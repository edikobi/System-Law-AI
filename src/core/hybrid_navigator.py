# src/core/hybrid_navigator.py
import sys
from pathlib import Path
from typing import List, Dict
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import Config
from src.core.law_navigator import LawNavigator
from src.rag.local_semantic_rag import LocalSemanticRAG
from src.core.simple_law_parser import SimpleLawParser

class HybridNavigator:
    """Гибридный навигатор: rule-based + семантический поиск"""
    
    def __init__(self):
        self.config = Config()
        self.project_root = Path(__file__).parent.parent.parent
        self.laws_dir = self.project_root / "laws"
        
        # Инициализируем оба поисковых движка
        print("🔄 Инициализация rule-based навигатора...")
        self.rule_based_navigator = LawNavigator()
        print("🔄 Инициализация семантического RAG...")
        self.semantic_rag = LocalSemanticRAG()
        
        # Индексируем законы при инициализации
        self._index_laws()
        
        print("✅ Гибридный навигатор инициализирован")
    
    @property
    def law_structures(self):
        """Делегирует доступ к структурам законов из rule-based навигатора"""
        return self.rule_based_navigator.law_structures

    def get_full_chapter_content(self, chapter: Dict) -> str:
        """
        Собирает полный текст главы со всеми дочерними структурными единицами.
        Делегирует вызов rule-based навигатору.
        """
        return self.rule_based_navigator.get_full_chapter_content(chapter)

    def _index_laws(self):
        """Индексирует законы в семантическом RAG"""
        print("📚 Индексация законов в семантическом RAG...")
        self.semantic_rag.index_law_chapters(self.rule_based_navigator.law_structures)
    
    def find_relevant_chapters(self, question: str, law_files: List[str], 
                             max_chapters: int = 5) -> List[Dict]:
        """Гибридный поиск релевантных глав"""
        print(f"🎯 Гибридный поиск: '{question}'")
        print(f"   📁 Законы для поиска: {law_files}")
        
        # Этап 1: Быстрый rule-based поиск
        print("   🔍 Этап 1: Rule-based поиск...")
        rule_based_start = time.time()
        rule_based_results = self.rule_based_navigator.find_relevant_chapters(
            question, law_files, max_chapters
        )
        rule_based_time = time.time() - rule_based_start
        
        # Фильтруем результаты с высокой релевантностью
        high_relevance_results = [
            r for r in rule_based_results 
            if r.get('relevance', 0) > 0.6
        ]
        
        print(f"   📊 Rule-based: {len(high_relevance_results)} высокорелевантных глав (время: {rule_based_time:.2f}с)")
        
        # Если нашли достаточно высокорелевантных результатов, возвращаем их
        if len(high_relevance_results) >= 2:
            print("   ✅ Используем rule-based результаты")
            for i, result in enumerate(high_relevance_results[:max_chapters], 1):
                print(f"      {i}. {result['law']} - {result['title'][:50]}... (релевантность: {result['relevance']:.2f})")
            return high_relevance_results[:max_chapters]
        
        # Этап 2: Семантический поиск если rule-based не сработал
        print("   🔍 Этап 2: Семантический поиск...")
        semantic_start = time.time()
        semantic_results = self.semantic_rag.semantic_search(
            question, law_files, max_chapters
        )
        semantic_time = time.time() - semantic_start
        
        print(f"   📊 Semantic: {len(semantic_results)} глав (время: {semantic_time:.2f}с)")
        
        # Объединяем и ранжируем результаты
        all_results = self._merge_and_rank_results(
            rule_based_results, 
            semantic_results, 
            max_chapters
        )
        
        print(f"   📊 Итог: {len(all_results)} глав (rule-based: {len(rule_based_results)}, semantic: {len(semantic_results)})")
        
        # Логируем итоговые результаты
        for i, result in enumerate(all_results, 1):
            match_type = result.get('match_type', 'unknown')
            relevance = result.get('relevance', 0)
            print(f"      {i}. [{match_type}] {result['law']} - {result['title'][:50]}... (релевантность: {relevance:.2f})")
        
        return all_results
    
    def find_relevant_containers(self, question: str, law_files: List[str], top_k: int = 5) -> List[Dict]:
        """
        Прокси-метод для вызова иерархического поиска контейнеров в семантическом RAG.
        Делегирует выполнение в self.semantic_rag.
        """
        # Проверяем, есть ли у semantic_rag нужный метод
        if hasattr(self.semantic_rag, 'find_relevant_containers'):
            return self.semantic_rag.find_relevant_containers(question, law_files, top_k)
        
        # Если метода нет (например, semantic_rag - это старая версия), 
        # пробуем получить доступ к коллекции напрямую, если это SmartLawRAG
        # Или просто возвращаем пустой список с предупреждением
        print("⚠️ Внимание: semantic_rag не поддерживает find_relevant_containers.")
        return []
    
    
    def _merge_and_rank_results(self, rule_results: List[Dict], 
                              semantic_results: List[Dict], 
                              max_chapters: int) -> List[Dict]:
        """Объединяет и ранжирует результаты от обоих методов"""
        # Создаем словарь для объединения результатов
        merged = {}
        
        # Добавляем rule-based результаты
        for result in rule_results:
            key = f"{result['law']}_{result['title']}"
            if key not in merged or result.get('relevance', 0) > merged[key].get('relevance', 0):
                merged[key] = result
                merged[key]['match_type'] = 'rule_based'
        
        # Добавляем семантические результаты
        for result in semantic_results:
            key = f"{result['law']}_{result['title']}"
            # Увеличиваем вес семантических результатов
            boosted_relevance = result['relevance'] * 1.2  # Бонус за семантику
            if key in merged:
                # Если глава уже есть, берем максимальную релевантность
                if boosted_relevance > merged[key].get('relevance', 0):
                    merged[key]['relevance'] = boosted_relevance
                    merged[key]['match_type'] = 'hybrid'
            else:
                result['relevance'] = boosted_relevance
                result['match_type'] = 'semantic'
                merged[key] = result
        
        # Сортируем по релевантности и берем топ
        sorted_results = sorted(
            merged.values(), 
            key=lambda x: x.get('relevance', 0), 
            reverse=True
        )
        
        return sorted_results[:max_chapters]

    def get_context_for_ai(self, chapters: list, category: str = None, question: str = None) -> dict:
        """Контекст для ИИ с информацией о найденных главах"""
        if not chapters:
            return {
                'context': "RAG не нашел релевантных глав для анализа",
                'analysis': "Рекомендуется автономный поиск статей ИИ",
                'priority_laws': [],
                'recommendations': []
            }
        
        # Форматируем контекст
        context_parts = []
        context_parts.append("🎯 РЕЛЕВАНТНЫЕ ГЛАВЫ ДЛЯ АНАЛИЗА")
        context_parts.append("=" * 60)
        context_parts.append(f"📂 Категория: {category}")
        context_parts.append(f"❓ Вопрос: {question}")
        context_parts.append(f"📊 Найдено глав: {len(chapters)}")
        context_parts.append("")
        
        for i, chapter in enumerate(chapters, 1):
            relevance = chapter.get('relevance', 0)
            relevance_indicator = "🔴" if relevance < 0.3 else "🟡" if relevance < 0.7 else "🟢"
            match_type = chapter.get('match_type', 'unknown')
            
            context_parts.append(f"{relevance_indicator} {i}. {chapter['law']} [{match_type}]")
            context_parts.append(f"   Заголовок: {chapter['title']}")
            context_parts.append(f"   Релевантность: {relevance:.2f}")
            
            # Краткое превью содержания
            content_preview = chapter['content'][:200].replace('\n', ' ')
            if len(chapter['content']) > 200:
                content_preview += "..."
            context_parts.append(f"   Превью: {content_preview}")
            context_parts.append("")
        
        context_parts.append("💡 РЕКОМЕНДАЦИИ ДЛЯ ИИ:")
        context_parts.append("-" * 30)
        context_parts.append("1. Анализируйте предложенные главы на релевантность вопросу")
        context_parts.append("2. Ищите конкретные статьи и нормы в этих главах")
        context_parts.append("3. Учитывайте релевантность при выборе источников")
        context_parts.append("4. [rule_based] - результат ключевых слов")
        context_parts.append("5. [semantic] - результат семантического поиска") 
        context_parts.append("6. [hybrid] - комбинированный результат")
        
        return {
            'context': "\n".join(context_parts),
            'analysis': f"Найдено {len(chapters)} релевантных глав",
            'priority_laws': list(set(chapter['law'] for chapter in chapters)),
            'recommendations': ["Использовать найденные главы как основу для поиска конкретных статей"],
            'coverage_quality': "good" if len(chapters) >= 3 else "moderate" if len(chapters) >= 1 else "poor"
        }

class EnhancedHybridNavigator(HybridNavigator):
    """Расширенный навигатор с поддержкой разных типов документов"""
    
    def __init__(self):
        # Инициализируем родительский класс полностью
        super().__init__()
        self.simple_parser = SimpleLawParser()
        
        # Перестраиваем структуры с учетом новых типов документов
        self._rebuild_law_structures_enhanced()
        
        print("✅ Улучшенный гибридный навигатор инициализирован")
    
    def get_full_chapter_content(self, chapter: Dict) -> str:
        """
        Собирает полный текст главы со всеми дочерними структурными единицами.
        Делегирует вызов rule-based навигатору.
        """
        return self.rule_based_navigator.get_full_chapter_content(chapter)
    
    def _rebuild_law_structures_enhanced(self):
        """Перестраивает структуры законов с поддержкой простых документов"""
        print("📚 Перестраиваю структуры с учетом типов документов...")
        
        for law_file in self.laws_dir.glob("*.txt"):
            if law_file.name not in self.rule_based_navigator.law_structures:
                # Для новых файлов используем улучшенный парсер
                content = self._read_law_file(law_file)
                if content:
                    doc_type = self._get_document_type(law_file.name)
                    
                    if doc_type == "codes":
                        # Используем существующий парсер для кодексов
                        structures = self.rule_based_navigator.parser.parse_law_major_structures(content, law_file.name)
                    else:
                        # Используем новый парсер для простых документов
                        structures = self.simple_parser.parse_simple_structure(content, law_file.name)
                    
                    self.rule_based_navigator.law_structures[law_file.name] = {
                        'structure': structures,
                        'full_content': content,
                        'document_type': doc_type
                    }
                    print(f"   ✅ {law_file.name} ({doc_type}): {len(structures)} структур")
    
    def _read_law_file(self, law_file: Path) -> str:
        """Безопасное чтение контента (поддержка .txt и .docx)"""
        
        # 1. Обработка DOCX
        if law_file.suffix.lower() == '.docx':
            try:
                import docx
                doc = docx.Document(law_file)
                # Просто склеиваем весь текст (для целей индексации/поиска)
                return '\n'.join([para.text for para in doc.paragraphs])
            except Exception as e:
                print(f"❌ Ошибка чтения DOCX {law_file.name}: {e}")
                return ""

        # 2. Обработка TXT (Старая логика)
        for encoding in ['utf-8', 'windows-1251', 'cp1251']:
            try:
                with open(law_file, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return ""
    
    def _get_document_type(self, law_file: str) -> str:
        """Определяет тип документа"""
        codes = getattr(self.config, 'DOCUMENT_TYPES', {}).get('codes', [])
        plenums = getattr(self.config, 'DOCUMENT_TYPES', {}).get('plenums', [])
        sublegal = getattr(self.config, 'DOCUMENT_TYPES', {}).get('sublegal', [])
        
        if law_file in codes:
            return "codes"
        elif law_file in plenums:
            return "plenums"
        elif law_file in sublegal:
            return "sublegal"
        else:
            return "codes"  # по умолчанию
    
    def _get_available_document_types(self, law_files: List[str], category: str) -> List[str]:
        """Определяет какие типы документов действительно доступны для категории"""
        available_types = set()
        
        for law_file in law_files:
            doc_type = self._get_document_type(law_file)
            available_types.add(doc_type)
        
        # Получаем приоритетный порядок для категории
        category_data = self.config.LEGAL_CATEGORIES.get(category, {})
        priority_order = category_data.get(
            "document_priority", ["codes", "plenums", "sublegal"]
        )
        
        # Фильтруем только доступные типы, сохраняя порядок приоритета
        available_ordered = [t for t in priority_order if t in available_types]
        
        print(f"   📊 Доступные типы документов для '{category}': {available_ordered}")
        return available_ordered

    def find_relevant_chapters_priority(self, question: str, law_files: List[str], 
                                      category: str, max_chapters: int = 8) -> List[Dict]:
        """Многоуровневый поиск с приоритетами по типам документов"""
        
        print(f"   🎯 Приоритетный поиск для категории '{category}'")
        print(f"   📁 Всего файлов: {len(law_files)}")
        
        # Используем новый метод для определения доступных типов
        available_types = self._get_available_document_types(law_files, category)
        
        print(f"   🎯 Приоритеты поиска: {available_types}")
        
        if not available_types:
            print(f"   ⚠️ Нет доступных типов документов, использую обычный поиск")
            return self.find_relevant_chapters(question, law_files, max_chapters)
        
        all_results = []
        
        for doc_type in available_types:
            # Фильтруем файлы по типу
            type_files = [f for f in law_files if self._get_document_type(f) == doc_type]
            
            if not type_files:
                continue
                
            print(f"   🔍 Поиск в {doc_type}: {len(type_files)} файлов")
            if len(type_files) <= 5:
                print(f"      Файлы: {', '.join(type_files)}")
            
            # Распределяем квоты пропорционально
            remaining_chapters = max_chapters - len(all_results)
            if remaining_chapters <= 0:
                break
                
            remaining_types = len(available_types) - available_types.index(doc_type)
            chapters_per_type = max(1, remaining_chapters // remaining_types)
            
            print(f"      Квота: {chapters_per_type} глав")
            
            # Ищем в файлах этого типа
            type_results = self._find_in_document_type(question, type_files, doc_type, chapters_per_type)
            all_results.extend(type_results)
            
            if type_results:
                print(f"   ✅ Найдено в {doc_type}: {len(type_results)} глав")
            else:
                print(f"   ⚠️ В {doc_type} не найдено релевантных глав")
        
        # Сортируем все результаты по релевантности
        all_results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        
        result_by_type = {}
        for result in all_results:
            doc_type = self._get_document_type(result['law'])
            if doc_type not in result_by_type:
                result_by_type[doc_type] = 0
            result_by_type[doc_type] += 1
        
        type_summary = ", ".join([f"{k}: {v}" for k, v in result_by_type.items()])
        print(f"   📊 Итоговый результат: {len(all_results)} глав ({type_summary})")
        
        return all_results[:max_chapters]
    
    def _find_in_document_type(self, question: str, law_files: List[str], 
                             doc_type: str, max_chapters: int) -> List[Dict]:
        """Поиск в конкретном типе документов"""
        
        if doc_type == "codes":
            return super().find_relevant_chapters(question, law_files, max_chapters)
        else:
            return self.semantic_rag.semantic_search(question, law_files, max_chapters)
    
    def get_context_for_ai_enhanced(self, chapters: list, category: str = None, question: str = None) -> dict:
        """Улучшенный контекст с информацией о типах документов"""
        context_data = super().get_context_for_ai(chapters, category, question)
        
        if chapters:
            doc_types = {}
            for chapter in chapters:
                law_name = chapter.get('law', 'Unknown')
                doc_type = self._get_document_type(law_name)
                if doc_type not in doc_types:
                    doc_types[doc_type] = []
                doc_types[doc_type].append(law_name)
            
            type_info = ["📊 ТИПЫ ДОКУМЕНТОВ В РЕЗУЛЬТАТАХ:"]
            for doc_type, laws in doc_types.items():
                type_name = {
                    'codes': 'Кодексы/Законы',
                    'plenums': 'Пленумы ВС РФ', 
                    'sublegal': 'Подзаконные акты'
                }.get(doc_type, doc_type)
                type_info.append(f"   {type_name}: {', '.join(laws)}")
            
            context_data['document_types'] = "\n".join(type_info)
            context_data['full_context'] = context_data.get('context', '') + "\n\n" + "\n".join(type_info)
        
        return context_data