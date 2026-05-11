# src/rag/smart_rag_simple.py

import chromadb
import chromadb.errors
from sentence_transformers import SentenceTransformer
import os
import re
import shutil
import sys
import gc
import time
import platform
import json
from pathlib import Path
from typing import Dict, Optional

# Добавляем корень проекта в sys.path для импорта config
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import Config
from src.core.law_navigator import EnhancedLawParser
from src.core.simple_law_parser import SimpleLawParser
from src.core.docx_intelligent_parser import DocxIntelligentParser


def read_file_with_encoding(file_path: Path) -> str:
    """Читает файл с автоматическим определением кодировки"""
    try:
        # Сначала пробуем UTF-8
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            # Пробуем Windows-1251
            with open(file_path, 'r', encoding='windows-1251') as f:
                content = f.read()
                print(f"   ✅ Прочитан с кодировкой: windows-1251")
                return content
        except UnicodeDecodeError:
            # Если не получилось, используем utf-8 с игнорированием ошибок
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            print(f"   ⚠️  Прочитан с игнорированием ошибок кодировки")
            return content


class SmartRAGSystem:
    # Статические атрибуты класса (кэшируемые между экземплярами)
    _embedding_model = None
    _LAW_FILES_CACHE_FILENAME = "law_files_cache.json"
    _chroma_client = None  # Singleton клиент ChromaDB
    _chroma_path = None    # Путь к текущей базе данных

    def __init__(self, auto_index: bool = True, force_reindex: bool = False):
        self.config = Config()

        # Кэширование модели эмбеддингов
        if SmartRAGSystem._embedding_model is None:
            print("🔧 Загрузка мультиязычной модели эмбеддингов...")
            SmartRAGSystem._embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("✅ Модель загружена")
        else:
            print("✅ Модель эмбеддингов уже загружена (используется кэшированная)")

        self.embedding_model = SmartRAGSystem._embedding_model

        # Определяем корень проекта
        self.project_root = Path(__file__).parent.parent.parent
        self.laws_dir = self.project_root / "laws"
        self.chroma_path = self.project_root / "chroma_db"
        self.descriptions_path = self.project_root / "chapter_descriptions.json"
        self.law_index_path = self.project_root / "law_index.json"

        print(f"🔧 Инициализация RAG системы:")
        print(f"   Корень проекта: {self.project_root}")
        print(f"   Папка законов: {self.laws_dir}")
        print(f"   Папка chroma_db: {self.chroma_path}")

        # Загружаем описания глав если есть
        self.chapter_descriptions = {}
        if self.descriptions_path.exists():
            try:
                with open(self.descriptions_path, 'r', encoding='utf-8') as f:
                    self.chapter_descriptions = json.load(f)
                print(f"✅ Загружено {len(self.chapter_descriptions)} описаний глав")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки описаний: {e}")

        # 🔥 НОВОЕ: Загружаем индекс законов
        self.law_index = {}
        if self.law_index_path.exists():
            try:
                with open(self.law_index_path, 'r', encoding='utf-8') as f:
                    self.law_index = json.load(f)
                print(f"✅ Загружен индекс: {len(self.law_index)} законов")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки индекса: {e}")
        else:
            print("⚠️ law_index.json не найден. Запустите --index для индексации")

        # Проверяем реальные файлы
        self._check_actual_filenames()

        # Создаем папку chroma_db если не существует
        self.chroma_path.mkdir(exist_ok=True)

        # ЕДИНОЖДЫ инициализируем ChromaDB клиент с обработкой ошибки
        self.client = None
        self.collection = None
    
        try:
            # Проверяем singleton клиент - сравниваем по пути
            if (SmartRAGSystem._chroma_client is not None and 
                SmartRAGSystem._chroma_path is not None and
                str(SmartRAGSystem._chroma_path) == str(self.chroma_path)):
                print("✅ Переиспользую существующий клиент ChromaDB")
                self.client = SmartRAGSystem._chroma_client
            else:
                # Если был старый клиент с другим путём - закрываем его
                if SmartRAGSystem._chroma_client is not None:
                    print("🔄 Закрываю старый клиент ChromaDB (путь изменился)")
                    self._close_chroma_client()
                
                print("🔧 Инициализирую новый клиент ChromaDB")
                self.client = chromadb.PersistentClient(path=str(self.chroma_path))
                SmartRAGSystem._chroma_client = self.client
                SmartRAGSystem._chroma_path = self.chroma_path
        except chromadb.errors.InternalError as e:
            if "no such table: tenants" in str(e):
                print("⚠️ Обнаружено повреждение базы данных ChromaDB (no such table: tenants)")
                print("🔄 Освобождаю ресурсы и очищаю поврежденную базу...")
                self._close_chroma_client()
                self._safe_remove_directory(self.chroma_path)
                self.chroma_path.mkdir(exist_ok=True)
                time.sleep(2.0 if platform.system() == 'Windows' else 0.5)
                print("🔄 Повторная инициализация ChromaDB...")
                try:
                    self.client = chromadb.PersistentClient(path=str(self.chroma_path))
                    SmartRAGSystem._chroma_client = self.client
                    SmartRAGSystem._chroma_path = self.chroma_path
                except chromadb.errors.InternalError as retry_error:
                    print(f"❌ Ошибка при повторной инициализации ChromaDB: {retry_error}")
                    raise
            else:
                raise

        # Инициализируем коллекцию
        self.collection = self.client.get_or_create_collection("legal_laws")

        # Инициализация парсеров
        self.enhanced_parser = EnhancedLawParser()
        self.simple_parser = SimpleLawParser()
        self.docx_parser = DocxIntelligentParser()

        # Улучшенная логика проверки и переиндексации
        try:
            # Шаг 1: Проверить изменения файлов
            files_changed = self._check_law_files_changes()

            # Шаг 2: Проверить целостность векторной базы
            collection_count = self.collection.count()

            # Шаг 3: Определить необходимость переиндексации
            needs_reindex = False

            if force_reindex:
                print("🔄 Принудительная переиндексация запрошена")
                needs_reindex = True
            elif files_changed:
                print("🔄 Обнаружены изменения в файлах законов, требуется переиндексация")
                needs_reindex = True
            elif collection_count == 0:
                print("🔄 Коллекция пуста или обнаружены изменения, начинаю индексацию законов...")
                needs_reindex = True
            else:
                print(f"✅ Векторная база цела, документов: {collection_count}")

            # Шаг 4: Выполнить переиндексацию если требуется
            if needs_reindex and (auto_index or force_reindex):
                self._index_laws()
                self._save_law_files_cache()
            else:
                # Шаг 5: Обновить кэш если переиндексация не требуется
                self._save_law_files_cache()

        except Exception as e:
            print(f"⚠️ Ошибка при проверке состояния базы: {e}")
            self._save_law_files_cache()

        # Запускаем диагностику
        self._run_diagnostics()

    def _get_document_type(self, law_file: str) -> str:
        """Определяет тип документа для чанкирования"""
        codes = [
            "trudovoy_kodeks.docx", "semeiniy_kodeks.docx", "gk_rf_1.docx", 
            "gk_rf_2.docx", "gk_rf_3.docx", "gk_rf_4.docx", "zhilishniy_kodeks.docx", 
            "koap.docx", "fssp.docx", "pdd.docx", "police.docx", "bankrotstvo.docx", "zpp.docx", "Postanov Mos o MKD.docx", 
            "Postanov o mkd 354.docx", "Post pravit N 290.docx"
        ]
        
        # Определяем пленумы по наличию "Plenum" в названии
        plenums = [f.name for f in self.laws_dir.glob("*") if f.name.startswith("Plenum") and f.suffix in ['.txt', '.docx']]
        
        sublegal = [
            "postanov o neusto k dolevoi.docx", 
            "zakon dolevoi.docx", "Postanov o mrk 491.docx", "Post Gosstoya.docx",
        ]
        
        if law_file in codes:
            return "codes"
        elif law_file in plenums:
            return "plenums"
        elif law_file in sublegal:
            return "sublegal"
        else:
            return "codes"  # по умолчанию

    def _run_diagnostics(self):
        """Запускает диагностику после инициализации"""
        if self.collection.count() > 0:
            print(f"\n" + "="*50)
            print("🔧 ЗАПУСК ДИАГНОСТИКИ RAG СИСТЕМЫ")
            print("="*50)
            self.diagnose_metadata()
            self.test_filters()
            self._verify_chroma_content()
            self.check_new_laws()
            print("="*50)
    
    def _check_actual_filenames(self):
        """Проверяет реальные имена файлов в папке laws"""
        print(f"\n📁 РЕАЛЬНЫЕ ФАЙЛЫ В ПАПКЕ LAWS:")
        
        if not self.laws_dir.exists():
            print(f"   ❌ Папка {self.laws_dir} не существует!")
            print(f"   💡 Создайте папку 'laws' в корне проекта и добавьте туда .txt файлы с законами")
            return
        
        # Берем все файлы (txt и docx), исключая служебные
        law_files = [f for f in self.laws_dir.glob("*") if f.suffix in ['.txt', '.docx']]

        
        # Сортируем для удобства сравнения
        actual_files = sorted([f.name for f in law_files])
        print(f"   Файлы на диске: {actual_files}")
        
        # Какие законы ожидаются в конфиге
        expected_laws = set()
        for category in self.config.LEGAL_CATEGORIES.values():
            expected_laws.update(category["laws"])
        
        expected_laws = sorted(list(expected_laws))
        print(f"   Ожидаемые в конфиге: {expected_laws}")
        
        # Сравниваем
        missing_files = set(expected_laws) - set(actual_files)
        extra_files = set(actual_files) - set(expected_laws)
        
        if missing_files:
            print(f"   ❌ Отсутствуют файлы: {list(missing_files)}")
        if extra_files:
            print(f"   ⚠️  Лишние файлы: {list(extra_files)}")

    def _check_law_files_changes(self) -> bool:
        """Проверяет изменились ли файлы законов с момента последней индексации"""
        cache_path = self.project_root / self._LAW_FILES_CACHE_FILENAME

        # Если файл кэша не существует, требуется индексация
        if not cache_path.exists():
            print("🔍 Проверка изменений файлов законов...")
            print("   Кэш не найден, требуется индексация")
            return True

        # Загружаем кэш
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception as e:
            print(f"🔍 Проверка изменений файлов законов...")
            print(f"   Ошибка чтения кэша: {e}, требуется переиндексация")
            return True

        # Получаем текущий список файлов
        current_files = {}
        if self.laws_dir.exists():
            for file_path in self.laws_dir.glob("*"):
                if file_path.suffix in ['.txt', '.docx']:
                    try:
                        mtime = os.path.getmtime(file_path)
                        current_files[file_path.name] = mtime
                    except Exception:
                        pass

        # Сравниваем
        print("🔍 Проверка изменений файлов законов...")

        # Проверяем количество файлов
        if len(current_files) != len(cache):
            print(f"   Количество файлов изменилось: {len(cache)} -> {len(current_files)}")
            return True

        # Проверяем каждый файл
        for filename, mtime in current_files.items():
            if filename not in cache:
                print(f"   Новый файл: {filename}")
                return True
            if cache[filename] != mtime:
                print(f"   Файл изменился: {filename}")
                return True

        # Проверяем удаленные файлы
        for filename in cache:
            if filename not in current_files:
                print(f"   Файл удален: {filename}")
                return True

        print("   Файлы не изменились")
        return False

    def _save_law_files_cache(self) -> None:
        """Сохраняет кэш файлов законов с их временем модификации"""
        cache = {}

        # Проходим по всем файлам в laws_dir
        if self.laws_dir.exists():
            for file_path in self.laws_dir.glob("*"):
                if file_path.suffix in ['.txt', '.docx']:
                    try:
                        mtime = os.path.getmtime(file_path)
                        cache[file_path.name] = mtime
                    except Exception:
                        pass

        # Записываем кэш в JSON файл
        cache_path = self.project_root / self._LAW_FILES_CACHE_FILENAME
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"💾 Кэш файлов законов сохранён ({len(cache)} файлов)")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения кэша: {e}")
    
    def clear_database(self):
        """Очищает векторную базу данных с корректным закрытием соединений"""
        # Сначала закрываем соединения
        self._close_chroma_client()
    
        # Затем безопасно удаляем директорию
        if self.chroma_path.exists():
            success = self._safe_remove_directory(self.chroma_path)
            if success:
                print(f"🗑️ База данных очищена: {self.chroma_path}")
            else:
                print(f"⚠️ Не удалось полностью очистить базу данных: {self.chroma_path}")
        else:
            print(f"ℹ️ База данных не найдена: {self.chroma_path}")
    
    def diagnose_metadata(self):
        """Диагностика метаданных в коллекции"""
        print(f"\n🔍 ДИАГНОСТИКА МЕТАДАННЫХ:")
        print(f"   Всего документов: {self.collection.count()}")
        
        # Получаем несколько документов для анализа
        sample = self.collection.get(limit=5)
        if sample['ids']:
            print("   Примеры метаданных:")
            for i, metadata in enumerate(sample['metadatas']):
                print(f"   Документ {i+1}: {metadata}")
        else:
            print("   ❌ Коллекция пуста!")
        
        # Проверяем уникальные значения поля 'law'
        all_data = self.collection.get()
        if all_data['metadatas']:
            laws = set(meta['law'] for meta in all_data['metadatas'])
            print(f"   Уникальные законы в базе: {list(laws)}")
    
    def test_filters(self):
        """Тестирование фильтров с реальными данными из базы"""
        print(f"\n🧪 ТЕСТИРОВАНИЕ ФИЛЬТРОВ:")
        
        # Сначала посмотрим какие законы реально есть в базе
        all_data = self.collection.get()
        if not all_data['metadatas']:
            print("   ❌ База данных пуста!")
            return
        
        real_laws = list(set(meta['law'] for meta in all_data['metadatas']))
        print(f"   Реальные законы в базе: {real_laws}")
        
        # Тестируем фильтры с реальными именами
        if real_laws:
            test_law = real_laws[0]
            print(f"\n🧪 Фильтр по реальному закону ($eq):")
            print(f"   Фильтр: {{'law': {{'$eq': '{test_law}'}}}}")
            
            query_embedding = self.embedding_model.encode("тест").tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=3,
                where={"law": {"$eq": test_law}}
            )
            
            if results['documents'] and results['documents'][0]:
                print(f"   ✅ Найдено документов: {len(results['documents'][0])}")
                for i, doc in enumerate(results['documents'][0]):
                    print(f"      {i+1}. {doc[:100]}...")
            else:
                print(f"   ❌ Документы не найдены")
    
    def _verify_chroma_content(self):
        """Проверяет что именно сохранилось в ChromaDB"""
        print(f"\n📊 СОДЕРЖИМОЕ CHROMADB ПО ЗАКОНАМ:")
        
        all_data = self.collection.get()
        if not all_data['metadatas']:
            print("   ❌ База пуста!")
            return
        
        # Группируем по законам
        laws_dict = {}
        for metadata in all_data['metadatas']:
            law_name = metadata['law']
            if law_name not in laws_dict:
                laws_dict[law_name] = 0
            laws_dict[law_name] += 1
        
        print(f"   Документы по законам:")
        for law, count in sorted(laws_dict.items()):
            print(f"     {law}: {count} документов")
            
        # Проверяем соответствие с файлами
        law_files = [f.name for f in self.laws_dir.glob("*") if f.suffix in ['.txt', '.docx']]
        missing_in_chroma = set(law_files) - set(laws_dict.keys())
        if missing_in_chroma:
            print(f"   ❌ В ChromaDB отсутствуют: {list(missing_in_chroma)}")

    def check_new_laws(self):
        """Проверяет наличие новых законов и при необходимости переиндексовывает"""
        print(f"\n🔍 ПРОВЕРКА НОВЫХ ЗАКОНОВ")
    
        # Получаем все ожидаемые законы из конфига
        expected_laws = set()
        for category in self.config.LEGAL_CATEGORIES.values():
            expected_laws.update(category["laws"])
    
        # Проверяем какие законы уже есть в базе
        all_data = self.collection.get()
        if not all_data['metadatas']:
            print("   ❌ База данных пуста, требуется полная индексация")
            return False
    
        laws_in_db = set(meta['law'] for meta in all_data['metadatas'])
    
        # Проверяем отсутствующие законы
        missing_laws = expected_laws - laws_in_db
    
        if missing_laws:
            print(f"   ⚠️  В базе отсутствуют законы: {list(missing_laws)}")
            print(f"   🔄 Запуск переиндексации...")
            try:
                self._index_laws()
                self._save_law_files_cache()
                return True
            except Exception as e:
                print(f"   ⚠️ Ошибка при переиндексации: {e}")
                return False
        else:
            print(f"   ✅ Все законы из конфига присутствуют в базе")
            return False

    def _index_laws(self):
        """Индексирует законы из law_index.json (индексирует ОПИСАНИЯ, не полный текст)"""
        print(f"📚 Индексация законов из law_index.json...")
    
        if not self.law_index:
            print(f"❌ Индекс законов пуст. Запустите индексацию через --index")
            return
    
        total_indexed = 0
    
        for law_name, law_data in self.law_index.items():
            chapters = law_data.get("chapters", [])
        
            print(f"\n📄 {law_name}: {len(chapters)} глав")
        
            for i, chapter in enumerate(chapters):
                title = chapter.get("title", f"Глава {i+1}")
                description = chapter.get("description", "")
            
                if not description.strip():
                    continue
            
                # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Индексируем ОПИСАНИЕ, а не полный текст
                embedding = self.embedding_model.encode(description).tolist()
            
                self.collection.add(
                    embeddings=[embedding],
                    documents=[description],  # Сохраняем описание в ChromaDB
                    metadatas=[{
                        "law": law_name,
                        "article": title,
                        "point": "ai_indexed_chapter",
                        "level": chapter.get("level", 0),
                        "article_id": f"{law_name}_{i}",
                        "chunk_type": "ai_description"
                    }],
                    ids=[f"{law_name}_{i}_ai"]
                )
                total_indexed += 1
        
            print(f"   ✅ Индексировано: {len(chapters)} глав")
    
        print(f"\n{'='*60}")
        print(f"🎉 ИТОГО ИНДЕКСИРОВАНО: {total_indexed} описаний глав")
        print(f"{'='*60}")

    def _search_in_specific_laws(self, question: str, laws: list, top_k: int = 3) -> list:
        """Поиск в конкретных законах с улучшенной диагностикой"""
        if not laws:
            return []

        normalized_laws = [law.lower().strip() for law in laws]
        
        print(f"   🎯 Поиск в законах: {normalized_laws}")
        
        law_filter = {"law": {"$in": normalized_laws}}

        query_embedding = self.embedding_model.encode(question).tolist()

        try:
            filtered_docs = self.collection.get(where=law_filter)
            print(f"   📊 Документов по фильтру: {len(filtered_docs['ids'])}")
            
            if len(filtered_docs['ids']) == 0:
                print(f"   ⚠️  ВНИМАНИЕ: Фильтр не нашел ни одного документа!")
                all_laws = set(meta['law'] for meta in self.collection.get()['metadatas'])
                print(f"   📋 Доступные законы в базе: {list(all_laws)}")
                
        except Exception as e:
            print(f"   ⚠️ Ошибка при проверке фильтра: {e}")

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=law_filter
            )
        except Exception as e:
            print(f"   ❌ Ошибка запроса с фильтром: {e}")
            print(f"   🔄 Использую поиск без фильтра...")
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
                    "point": metadata.get("point", ""),
                    "level": metadata.get("level", 0),
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
                    "point": metadata.get("point", ""),
                    "level": metadata.get("level", 0),
                    "content": doc,
                    "relevance_score": 1 - distance,
                    "priority_weight": 1.0
                })
        
        return formatted_results
    
    def _merge_and_rank_results(self, *results_sets):
        """Объединяет и ранжирует результаты из разных уровней с учетом вложенности"""
        all_results = []
        
        for level, results in enumerate(results_sets):
            for result in results:
                priority_weight = 1.0 / (level + 1)
                
                point_level = result.get("level", 0)
                if point_level == 0:
                    priority_weight *= 1.0
                elif point_level == 1:
                    priority_weight *= 1.3
                elif point_level == 2:
                    priority_weight *= 1.5
                elif point_level >= 3:
                    priority_weight *= 1.8
                    
                result["priority_weight"] = priority_weight
                result["final_score"] = result["relevance_score"] * priority_weight
                all_results.append(result)
        
        return sorted(all_results, key=lambda x: x["final_score"], reverse=True)[:5]

    def search_with_priority(self, question: str, category: str) -> list:
        """Исправленная версия умного поиска с приоритетами"""
        print(f"🔍 Поиск по категории: {category}")
        
        category_config = self.config.LEGAL_CATEGORIES.get(category, self.config.LEGAL_CATEGORIES["unknown"])
        
        print(f"   Конфиг категории:")
        print(f"     Законы: {category_config['laws']}")
        
        if not category_config["laws"]:
            print("   ⚠️  Нет законов для поиска, использую поиск по всем")
            return self._search_all_laws(question)
        
        print(f"   🔍 Ищу в законах: {category_config['laws']}")
        results = self._search_in_specific_laws(question, category_config["laws"], top_k=10)
        print(f"     Найдено: {len(results)} статей")
        
        return results[:5]
    
    def find_relevant_containers(self, question: str, law_files: list, top_k: int = 15) -> list:
        """
        Ищет наиболее релевантные "контейнеры" (главы или разделы).
        Использует ChromaDB для поиска, но возвращает РЕАЛЬНЫЙ текст из файлов законов.
        """
        print("🚀 RAG-1: Запуск поиска контейнеров...")
        print(f"   Законы для поиска: {law_files}")
        print(f"   Максимум глав: {top_k}")

        query_embedding = self.embedding_model.encode(question).tolist()

        # Фильтр: ищем только в выбранных законах
        where_clause = {"law": {"$in": law_files}}

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause
            )
        except Exception as e:
            print(f"   ⚠️ Ошибка поиска: {e}")
            return []

        final_containers = []

        if not results or not results['documents'] or not results['documents'][0]:
            print("   ⚠️ Ничего не найдено")
            return []

        # Обработка результатов - читаем РЕАЛЬНЫЙ текст из файлов
        for i in range(len(results['documents'][0])):
            indexed_doc = results['documents'][0][i]  # Текст из индекса (fallback)
            meta = results['metadatas'][0][i]
            distance = results['distances'][0][i] if results['distances'] else 1.0

            law_name = meta.get('law', 'unknown_law')
            title = meta.get('article', 'Без названия')

            # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Читаем реальный текст из файла закона
            real_content = self._read_chapter_from_law_file(law_name, title)
        
            # Если не удалось прочитать из файла, используем текст из индекса
            if real_content:
                content = real_content
                print(f"   ✅ Загружен реальный текст: {law_name} / {title[:40]}...")
            else:
                content = indexed_doc
                print(f"   ⚠️ Используем индексированный текст: {law_name} / {title[:40]}...")

            # Получаем AI-описание если есть
            chunk_key = f"{law_name}_{title}"
            ai_description = self.chapter_descriptions.get(chunk_key, "")

            final_containers.append({
                'title': title,
                'content': content,
                'law': law_name,
                'type': meta.get('chunk_type', 'chapter'),
                'relevance_score': 1 - distance,
                'ai_description': ai_description,
                'source': 'file' if real_content else 'index'  # Для диагностики
            })

        # Сортируем по релевантности
        final_containers.sort(key=lambda x: x['relevance_score'], reverse=True)

        print(f"✅ RAG-1: Найдено {len(final_containers)} контейнеров")
        for i, c in enumerate(final_containers[:5], 1):
            source_icon = "📄" if c.get('source') == 'file' else "📦"
            print(f"   {i}. {source_icon} [{c['law']}] {c['title'][:50]}... (score: {c['relevance_score']:.2f})")

        return final_containers

    def _read_chapter_from_law_file(self, law_name: str, chapter_title: str) -> str:
        """
        Читает реальный текст главы из файла закона.
        Возвращает текст главы или пустую строку если не найдено.
        """
        try:
            law_path = self.laws_dir / law_name

            if not law_path.exists():
                print(f"      ⚠️ Файл закона не найден: {law_path}")
                return ""

            # Для DOCX файлов используем интеллектуальный парсер
            if law_name.lower().endswith('.docx'):
                try:
                    root = self.docx_parser.parse(str(law_path))
                    chunks = self.docx_parser.chunk_tree(root, max_chars=120000)

                    # Ищем чанк с подходящим заголовком
                    for chunk in chunks:
                        chunk_title = chunk.get('chunk_title', '')
                        # Проверяем совпадение заголовков (частичное)
                        if chapter_title.lower() in chunk_title.lower() or chunk_title.lower() in chapter_title.lower():
                            return chunk.get('content', '')

                    # Если точное совпадение не найдено, ищем по первым словам
                    chapter_words = chapter_title.lower().split()[:3]
                    for chunk in chunks:
                        chunk_title = chunk.get('chunk_title', '').lower()
                        if all(word in chunk_title for word in chapter_words if len(word) > 2):
                            return chunk.get('content', '')

                except Exception as e:
                    print(f"      ⚠️ Ошибка парсинга DOCX {law_name}: {e}")
                    return ""

            # Для TXT файлов используем текстовый поиск
            else:
                try:
                    content = read_file_with_encoding(law_path)

                    # Ищем начало главы по заголовку
                    lines = content.split('\n')
                    chapter_start = -1

                    for i, line in enumerate(lines):
                        if chapter_title.lower() in line.lower():
                            chapter_start = i
                            break

                    if chapter_start == -1:
                        return ""

                    # Ищем конец главы (следующая глава или раздел)
                    chapter_end = len(lines)
                    next_chapter_patterns = ['ГЛАВА', 'РАЗДЕЛ', 'Глава', 'Раздел']

                    for i in range(chapter_start + 1, len(lines)):
                        line = lines[i].strip()
                        if any(pattern in line for pattern in next_chapter_patterns) and len(line) < 200:
                            if i > chapter_start + 5:  # Минимум 5 строк в главе
                                chapter_end = i
                                break

                    return '\n'.join(lines[chapter_start:chapter_end])

                except Exception as e:
                    print(f"      ⚠️ Ошибка чтения TXT {law_name}: {e}")
                    return ""

            return ""

        except Exception as e:
            print(f"      ⚠️ Ошибка чтения главы из {law_name}: {e}")
            return ""

    def _close_chroma_client(self) -> None:
        """Корректно закрывает клиент ChromaDB и освобождает ресурсы"""
        try:
            if SmartRAGSystem._chroma_client is not None:
                try:
                    # Попытаемся закрыть клиент если доступен метод close
                    if hasattr(SmartRAGSystem._chroma_client, '_client') and hasattr(SmartRAGSystem._chroma_client._client, 'close'):
                        SmartRAGSystem._chroma_client._client.close()
                except Exception as e:
                    print(f"⚠️ Предупреждение при закрытии клиента: {e}")

                # Обнуляем ссылки
                SmartRAGSystem._chroma_client = None

            self.client = None
            self.collection = None

            # Освобождаем ресурсы
            gc.collect()

            # На Windows добавляем задержку для гарантии освобождения файлов
            if platform.system() == 'Windows':
                time.sleep(1.0)

        except Exception as e:
            print(f"⚠️ Ошибка при закрытии клиента ChromaDB: {e}")
            # Всё равно обнуляем ссылки
            SmartRAGSystem._chroma_client = None
            self.client = None
            self.collection = None

    def _safe_remove_directory(self, path: Path, max_retries: int = 5) -> bool:
        """Безопасно удаляет директорию с повторными попытками"""
        if not path.exists():
            return True

        # Определяем задержку между попытками
        base_delay = 1.0 if platform.system() == 'Windows' else 0.3

        for attempt in range(max_retries):
            try:
                shutil.rmtree(path)
                print(f"✅ Директория удалена: {path}")
                return True
            except (PermissionError, OSError) as e:
                if attempt < max_retries - 1:
                    # Освобождаем ресурсы и ждём перед следующей попыткой
                    gc.collect()
                    delay = base_delay * (attempt + 1)
                    print(f"⏳ Попытка {attempt + 1}/{max_retries} удаления {path.name}... (ожидание {delay:.1f}с)")
                    time.sleep(delay)
                else:
                    print(f"❌ Не удалось удалить директорию после {max_retries} попыток: {path}")
                    print(f"   Ошибка: {e}")
                    return False

        return False