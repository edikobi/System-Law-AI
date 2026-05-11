# src/rag/local_semantic_rag.py
import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os
from pathlib import Path
import sys
from typing import List, Dict, Tuple
import time
import chromadb.errors
import shutil

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import Config

import chromadb
from chromadb.utils import embedding_functions

class LocalSemanticRAG:
    """RAG-клиент, работающий с основной базой ChromaDB."""
    
    def __init__(self):  # Убираем model_name, он больше не нужен
        self.config = Config()
        self.project_root = Path(__file__).parent.parent.parent
        
        # Путь к нашей основной базе, созданной индексатором
        self.chroma_path = self.project_root / "chroma_db"
        
        print(f"🔧 Инициализация RAG-клиента к базе: {self.chroma_path}")
        
        if not self.chroma_path.exists():
            print("❌ ОШИБКА: База данных ChromaDB не найдена! Запустите индексацию.")
            self.collection = None
            return

        # Подключаемся к существующей ChromaDB
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
                        print("⚠️ Установка collection = None")
                        self.collection = None
                        return
                    else:
                        raise
        
        # Указываем ту же модель эмбеддингов, что и при индексации
        self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Получаем коллекцию с документами
        try:
            self.collection = self.client.get_collection(
                name="legal_laws",
                embedding_function=self.embedding_func
            )
            print(f"✅ Подключено к коллекции 'legal_docs'. Документов: {self.collection.count()}")
        except Exception as e:
            print(f"❌ Ошибка подключения к коллекции: {e}")
            self.collection = None
    
    def _load_embeddings_cache(self):
        """Загружает кэш эмбеддингов из файла"""
        if self.embeddings_cache_file.exists() and self.chapters_index_file.exists():
            try:
                with open(self.embeddings_cache_file, 'rb') as f:
                    self.chapter_embeddings = pickle.load(f)
                with open(self.chapters_index_file, 'rb') as f:
                    self.chapters_index = pickle.load(f)
                print(f"✅ Загружен кэш эмбеддингов: {len(self.chapter_embeddings)} глав")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки кэша: {e}. Создаем новый кэш.")
                self.chapter_embeddings = {}
                self.chapters_index = {}
        else:
            print("🔍 Кэш эмбеддингов не найден, будет создан новый")
    
    def _save_embeddings_cache(self):
        """Сохраняет кэш эмбеддингов в файл"""
        try:
            with open(self.embeddings_cache_file, 'wb') as f:
                pickle.dump(self.chapter_embeddings, f)
            with open(self.chapters_index_file, 'wb') as f:
                pickle.dump(self.chapters_index, f)
            print(f"💾 Кэш эмбеддингов сохранен: {len(self.chapter_embeddings)} глав")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения кэша: {e}")
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Получает эмбеддинг для текста"""
        if not text.strip():
            return np.zeros(312)  # Размерность для rubert-tiny2
        
        try:
            # Токенизация
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=512
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Получение эмбеддинга
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Берем эмбеддинг [CLS] токена
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
            
            return embedding
            
        except Exception as e:
            print(f"❌ Ошибка получения эмбеддинга: {e}")
            return np.zeros(312)
    
    def index_law_chapters(self, law_structures: Dict):
        """
        DEPRECATED: Индексация теперь выполняется через smart_rag_simple.py.
        Этот метод оставлен для совместимости с HybridNavigator, но он ничего не делает.
        """
        print("⚠️ [RAG] Пропуск index_law_chapters: используем готовую базу ChromaDB.")
        
        # Можно добавить проверку, есть ли данные в ChromaDB
        if self.collection and self.collection.count() == 0:
             print("❌ ВНИМАНИЕ: База ChromaDB пуста! Запустите run_indexing_and_report.py")
        
        return # Просто выходим, не пытаясь заполнять self.chapter_embeddings
    
    def find_relevant_containers(self, question: str, law_files: list, top_k: int = 5) -> list:
        """
        Ищет наиболее релевантные "контейнеры" (главы или разделы),
        используя иерархический подход (Главы -> Подчанки).
        """
        # Проверяем наличие коллекции
        if not hasattr(self, 'collection') or not self.collection:
            print("⚠️ Коллекция ChromaDB не инициализирована.")
            return []

        print("🚀 RAG-1: Запуск иерархического поиска контейнеров...")
        
        # Фильтр: ищем только в выбранных законах и только Уровень 0 (Главы/Разделы)
        where_clause = {
            "$and": [
                {"level": 0}, 
                {"law": {"$in": law_files}}
            ]
        }

        # 1. Поиск крупных контейнеров (level=0)
        print("   Этап 1: Поиск крупных контейнеров (level=0)...")
        try:
            results_level_0 = self.collection.query(
                query_texts=[question], # Chroma сама делает эмбеддинг
                n_results=top_k,
                where=where_clause
            )
        except Exception as e:
            print(f"   ⚠️ Ошибка поиска level=0: {e}. Пробую упрощенный поиск...")
            results_level_0 = self.collection.query(
                query_texts=[question],
                n_results=top_k,
                 where={"law": {"$in": law_files}}
            )

        final_containers = []
        
        if not results_level_0 or not results_level_0['documents']:
            print("   ⚠️ Ничего не найдено на уровне 0.")
            return []

        # 2. Обработка результатов
        for i in range(len(results_level_0['documents'][0])):
            doc = results_level_0['documents'][0][i]
            meta = results_level_0['metadatas'][0][i]
            
            char_count = len(doc)
            if 'char_count' in meta:
                char_count = meta['char_count']

            law_name = meta.get('law', 'unknown_law')
            title = meta.get('title') or meta.get('article') or 'Без названия'

            # ЛОГИКА: Если глава > 120к символов -> ищем в подчанках (level 1)
            if char_count > 120000:
                print(f"   ⚠️ Контейнер '{title}' слишком большой ({char_count} симв). Ныряем в подчанки (level=1)...")
                
                sub_results = self.collection.query(
                    query_texts=[question],
                    n_results=3,
                    where={
                        "$and": [
                            {"level": 1},
                            {"law": law_name}
                        ]
                    }
                )
                
                if sub_results['documents']:
                    for j in range(len(sub_results['documents'][0])):
                        sub_doc = sub_results['documents'][0][j]
                        sub_meta = sub_results['metadatas'][0][j]
                        final_containers.append({
                            'title': sub_meta.get('article', 'Подраздел'),
                            'content': sub_doc,
                            'law': sub_meta.get('law'),
                            'type': 'sub_chunk'
                        })
            else:
                # Если размер нормальный, берем главу целиком
                final_containers.append({
                    'title': title,
                    'content': doc,
                    'law': law_name,
                    'type': 'chapter'
                })

        print(f"✅ RAG-1: Найдено {len(final_containers)} контейнеров для анализа ИИ.")
        return final_containers
    
    def semantic_search(self, query: str, laws_filter: List[str] = None, top_k: int = 5) -> List[Dict]:
        """
        Семантический поиск релевантных глав (через ChromaDB).
        """
        # Проверка инициализации коллекции (заменяет проверку self.chapter_embeddings)
        if not hasattr(self, 'collection') or not self.collection:
             print("⚠️ Коллекция ChromaDB не инициализирована, поиск невозможен.")
             return []
        
        print(f"🔍 Семантический поиск (ChromaDB): '{query}'")
        start_time = time.time()
        
        try:
            # 1. Подготовка фильтра для ChromaDB
            where_filter = None
            if laws_filter:
                if len(laws_filter) == 1:
                    where_filter = {"law": laws_filter[0]}
                else:
                    # ChromaDB синтаксис для OR
                    where_filter = {"$or": [{"law": f} for f in laws_filter]}

            # 2. Выполнение запроса (Вместо self.get_embedding + cosine_similarity)
            # ChromaDB сама делает embedding и similarity search
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter
            )

            # 3. Сборка результатов в привычный для твоей системы формат
            final_results = []
            
            if not results or not results['ids']:
                 print("⚠️ Ничего не найдено в базе.")
                 return []

            # Итерируемся по найденным элементам
            # results['ids'][0] - это список ID первого запроса
            for i in range(len(results['ids'][0])):
                
                # Извлекаем данные
                chunk_id = results['ids'][0][i]
                meta = results['metadatas'][0][i]
                content = results['documents'][0][i]
                
                # Конвертируем distance в similarity (примерно)
                # Chroma использует L2 distance или Cosine distance. Обычно маленькая дистанция = большая похожесть.
                distance = results['distances'][0][i] if results['distances'] else 0.5
                similarity = 1 - distance # Грубая оценка, но подойдет для порога
                
                if similarity > 0.3: # Твой порог релевантности
                    # Формируем структуру, похожую на старый chapter_info
                    chapter_info = {
                        'id': chunk_id,
                        'title': meta.get('article', 'Без названия'), # В нашем парсере заголовок в поле 'article'
                        'content': content,
                        'law': meta.get('law', 'unknown'),
                        'type': meta.get('point', 'chunk'),
                        'level': meta.get('level', 0),
                        
                        # Поля, специфичные для поиска
                        'relevance': float(similarity),
                        'match_type': 'semantic'
                    }
                    final_results.append(chapter_info)

            search_time = time.time() - start_time
            print(f"✅ Найдено релевантных глав: {len(final_results)} (время: {search_time:.2f}с)")
            
            return final_results
            
        except Exception as e:
            print(f"❌ Ошибка семантического поиска в ChromaDB: {e}")
            import traceback
            traceback.print_exc()
            return []
