# src/rag/smart_rag_fixed.py
import chromadb
from sentence_transformers import SentenceTransformer
import os
from pathlib import Path
from config import Config
import chromadb.errors
import shutil

class SmartRAGSystem:
    def __init__(self):
        self.config = Config()
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Получаем абсолютный путь к корню проекта
        self.project_root = Path(__file__).parent.parent.parent
        print(f"📁 Корень проекта: {self.project_root}")
        
        # Абсолютные пути
        self.laws_dir = self.project_root / self.config.LAWS_DIR
        self.chroma_path = self.project_root / self.config.CHROMA_DIR
        
        print(f"🔧 Инициализация RAG системы:")
        print(f"   Законы: {self.laws_dir}")
        print(f"   ChromaDB: {self.chroma_path}")
        print(f"   Существует папка законов: {self.laws_dir.exists()}")
        
        try:
            self.client = chromadb.PersistentClient(path=str(self.chroma_path))
        except chromadb.errors.InternalError as e:
            if "no such table: tenants" in str(e):
                print("⚠️ Обнаружено повреждение базы данных ChromaDB (no such table: tenants)")
                print("🔄 Удаляю поврежденную базу и повторяю попытку...")
                if self.chroma_path.exists():
                    shutil.rmtree(self.chroma_path)
                    self.chroma_path.mkdir(exist_ok=True)
                    try:
                        self.client = chromadb.PersistentClient(path=str(self.chroma_path))
                    except chromadb.errors.InternalError as retry_error:
                        print(f"❌ Ошибка при повторной инициализации ChromaDB: {retry_error}")
                        raise
                    else:
                        raise
        
        # Инициализируем коллекцию
        self.collection = self.client.get_or_create_collection("legal_laws")
        
        # Индексируем законы при первом запуске
        if self.collection.count() == 0:
            print("🔄 Коллекция пуста, начинаю индексацию законов...")
            self._index_laws()
        else:
            count = self.collection.count()
            print(f"✅ В коллекции уже есть {count} документов")
    
    def _index_laws(self):
        """Индексирует все законы в векторной БД"""
        print(f"📚 Индексирую законы из: {self.laws_dir}")
        
        if not self.laws_dir.exists():
            print(f"❌ Папка с законами не существует: {self.laws_dir}")
            return
            
        law_files = list(self.laws_dir.glob("*.txt"))
        print(f"📄 Найдено .txt файлов: {len(law_files)}")
        
        for law_file in law_files:
            print(f"   📖 Обрабатываю: {law_file.name}")
            
            try:
                with open(law_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if not content.strip():
                    print(f"      ⚠️  Файл пустой: {law_file.name}")
                    continue
                
                # Разбиваем на статьи
                articles = self._split_into_articles(content, law_file.name)
                print(f"      📑 Извлечено статей: {len(articles)}")
                
                for i, (article_title, article_content) in enumerate(articles):
                    if not article_content.strip():
                        continue
                        
                    # Создаем embedding для статьи
                    embedding = self.embedding_model.encode(article_content).tolist()
                    
                    # Сохраняем в ChromaDB
                    self.collection.add(
                        embeddings=[embedding],
                        documents=[article_content],
                        metadatas=[{
                            "law": law_file.name,
                            "article": article_title,
                            "article_id": f"{law_file.name}_{i}"
                        }],
                        ids=[f"{law_file.name}_{i}"]
                    )
                
                print(f"      ✅ {law_file.name}: {len(articles)} статей добавлено")
                
            except Exception as e:
                print(f"      ❌ Ошибка обработки {law_file.name}: {e}")
                import traceback
                traceback.print_exc()
    
    def _split_into_articles(self, content: str, law_name: str) -> list:
        """Простой парсер статей из текста закона"""
        articles = []
        lines = content.split('\n')
        
        current_article = []
        current_title = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('Статья') or line.startswith('Глава') or line.startswith('СТАТЬЯ') or line.startswith('ГЛАВА'):
                if current_article and current_title:
                    articles.append((current_title, '\n'.join(current_article)))
                current_article = [line]
                current_title = line
            elif line and current_article:
                current_article.append(line)
        
        if current_article and current_title:
            articles.append((current_title, '\n'.join(current_article)))
        
        # Если не нашли статей по шаблону, используем весь контент как одну статью
        if not articles:
            articles.append((f"Закон {law_name}", content))
            print(f"      ℹ️  Использован весь файл как одна статья")
        
        return articles
    
    def search_with_priority(self, question: str, category: str) -> list:
        """Умный поиск с приоритетами по категории"""
        print(f"🔍 Поиск по категории: {category}")
        
        category_config = self.config.LEGAL_CATEGORIES.get(category, self.config.LEGAL_CATEGORIES["unknown"])
        
        if category_config["primary_laws"] == ["ALL"]:
            # Поиск по всем законам
            return self._search_all_laws(question)
        
        # Многоуровневый поиск
        primary_results = self._search_in_specific_laws(question, category_config["primary_laws"], top_k=3)
        secondary_results = self._search_in_specific_laws(question, category_config["secondary_laws"], top_k=2)
        related_results = self._search_in_specific_laws(question, category_config["related_laws"], top_k=1)
        
        return self._merge_and_rank_results(primary_results, secondary_results, related_results)
    
    def _search_in_specific_laws(self, question: str, laws: list, top_k: int = 3) -> list:
        """Поиск в конкретных законах"""
        if not laws:
            return []
        
        # Создаем фильтр для конкретных законов
        law_filter = {"law": {"$in": laws}}
        
        # Получаем эмбеддинг вопроса
        query_embedding = self.embedding_model.encode(question).tolist()
        
        # Ищем в ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=law_filter
        )
        
        # Форматируем результаты
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                formatted_results.append({
                    "law": metadata["law"],
                    "article": metadata["article"],
                    "content": doc,
                    "relevance_score": 1 - distance,
                    "priority_weight": 1.0
                })
        
        return formatted_results
    
    def _search_all_laws(self, question: str, top_k: int = 10) -> list:
        """Поиск по всем законам"""
        query_embedding = self.embedding_model.encode(question).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                formatted_results.append({
                    "law": metadata["law"],
                    "article": metadata["article"],
                    "content": doc,
                    "relevance_score": 1 - distance,
                    "priority_weight": 1.0
                })
        
        return formatted_results
    
    def _merge_and_rank_results(self, *results_sets):
        """Объединяет и ранжирует результаты из разных уровней"""
        all_results = []
        
        for level, results in enumerate(results_sets):
            for result in results:
                # Устанавливаем вес в зависимости от уровня
                result["priority_weight"] = 1.0 / (level + 1)
                result["final_score"] = result["relevance_score"] * result["priority_weight"]
                all_results.append(result)
        
        # Сортируем по итоговому score и берем топ-5
        return sorted(all_results, key=lambda x: x["final_score"], reverse=True)[:5]