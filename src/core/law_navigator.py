# src/core/law_navigator.py
import os
from pathlib import Path
from typing import List, Dict
import sys
import re
project_root = Path(__file__).parent.parent.parent

sys.path.insert(0, str(project_root))

from config import Config
# Добавить этот импорт вверху файла(это для нового разделения):
from src.core.simple_law_parser import SimpleLawParser
from src.core.docx_intelligent_parser import DocxIntelligentParser # импорт парсера для чанкирования законов для ИИ

class EnhancedLawParser:
    """Улучшенный парсер для выделения крупных структурных единиц законов"""
    
    def __init__(self):
        # Инициализация парсеров
        self.parser = self  # Для совместимости
        self.simple_parser = SimpleLawParser()
        self.docx_parser = DocxIntelligentParser()
        self.laws_dir = Path(__file__).parent.parent.parent / "laws"

        # Паттерны для определения крупных структурных единиц
        self.major_patterns = [
            # Разделы (SECTION)
            (r'^(РАЗДЕЛ\s+[IVXLCDM]+)\s*[\.\-—]\s*(.*)$', 'section'),
            (r'^(РАЗДЕЛ\s+\d+)\s*[\.\-—]\s*(.*)$', 'section'),
            (r'^(ЧАСТЬ\s+[IVXLCDM]+)\s*[\.\-—]\s*(.*)$', 'section'),
            (r'^(ЧАСТЬ\s+\d+)\s*[\.\-—]\s*(.*)$', 'section'),
            
            # Главы (CHAPTER)  
            (r'^(ГЛАВА\s+[IVXLCDM]+)\s*[\.\-—]\s*(.*)$', 'chapter'),
            (r'^(ГЛАВА\s+\d+)\s*[\.\-—]\s*(.*)$', 'chapter'),
            (r'^(ГЛАВА\s+\d+-\w+)\s*[\.\-—]\s*(.*)$', 'chapter'),
            
            # Крупные подразделы (SUBSECTION)
            (r'^(Подраздел\s+[IVXLCDM]+)\s*[\.\-—]\s*(.*)$', 'subsection'),
            (r'^(Подраздел\s+\d+)\s*[\.\-—]\s*(.*)$', 'subsection'),
            
            # Основные статьи (только нумерованные, без подпунктов)
            (r'^(Статья\s+\d+\.?\s*$)', 'major_article'),
            (r'^(СТАТЬЯ\s+\d+\.?\s*$)', 'major_article'),
        ]
        
    def parse_law_major_structures(self, content: str, law_name: str) -> List[Dict]:
        """Парсит только крупные структурные единицы закона. Поддерживает .txt и .docx"""
        
        # --- НОВАЯ ЛОГИКА: Если файл .docx, используем структурный парсер ---
        if law_name.lower().endswith('.docx'):
            # Пытаемся найти файл на диске, чтобы отдать его docx парсеру
            # (Так как docx_parser требует путь к файлу, а не строку контента)
            full_path = self.laws_dir / law_name
            if full_path.exists():
                try:
                    # Парсим структуру через docx
                    structures = self.docx_parser.parse_docx_structure(str(full_path), law_name)
                    
                    # Навигатор интересуют только крупные узлы (Главы - level 0, Разделы - level 1)
                    # Фильтруем только их
                    major_structures = [s for s in structures if s['level'] <= 1]
                    
                    # Если парсер вернул что-то, возвращаем это
                    if major_structures:
                        return major_structures
                    # Если структур не найдено (плоский docx), вернем пустой список
                    # и позволим коду ниже попробовать создать искусственные блоки (если нужно)
                    # или просто вернем как есть.
                    return structures # Вернем всё что нашли (даже если это просто full_document)
                except Exception as e:
                    print(f"⚠️ Ошибка парсинга DOCX структуры в навигаторе: {e}")
                    # Fallback к старой логике (парсить текст как txt)
            else:
                 print(f"⚠️ Файл {law_name} не найден на диске, пропускаю DOCX парсинг.")

        # --- СТАРАЯ ЛОГИКА: Regex парсинг (для .txt или если docx не сработал) ---
        major_structures = []
        lines = content.split('\n')
        
        current_structure = None
        current_content = []
        
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Проверяем, является ли строка началом крупной структурной единицы
            structure_type, title = self._identify_major_structure(line_clean)
            
            if structure_type:
                # Сохраняем предыдущую структуру если она есть
                if current_structure and current_content:
                    major_structures.append({
                        'type': current_structure['type'],
                        'title': current_structure['title'],
                        'content': '\n'.join(current_content),
                        'level': self._get_structure_level(current_structure['type']),
                        'size': len('\n'.join(current_content))
                    })
                
                # Начинаем новую крупную структуру
                current_structure = {
                    'type': structure_type,
                    'title': title or line_clean,
                    'original_line': line_clean
                }
                current_content = [line_clean]
                
            elif current_structure:
                # Продолжаем накапливать контент для текущей крупной структуры
                current_content.append(line_clean)
        
        # Добавляем последнюю структуру
        if current_structure and current_content:
            major_structures.append({
                'type': current_structure['type'],
                'title': current_structure['title'],
                'content': '\n'.join(current_content),
                'level': self._get_structure_level(current_structure['type']),
                'size': len('\n'.join(current_content))
            })
        
        # Если не нашли крупных структур, создаем искусственные крупные блоки
        if not major_structures:
            major_structures = self._create_major_blocks_from_content(content, law_name)
            
        return major_structures
    
    def _identify_major_structure(self, line: str) -> (str, str):
        """Определяет, является ли строка началом крупной структурной единицы"""
        for pattern, structure_type in self.major_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                # Извлекаем заголовок (последняя группа)
                groups = match.groups()
                title = groups[-1] if len(groups) > 1 else groups[0]
                return structure_type, title.strip()
        
        return None, ""
    
    def _get_structure_level(self, structure_type: str) -> int:
        """Определяет уровень вложенности структурной единицы"""
        levels = {
            'section': 1,
            'chapter': 2,
            'subsection': 3,
            'major_article': 4
        }
        return levels.get(structure_type, 5)
    
    def _create_major_blocks_from_content(self, content: str, law_name: str) -> List[Dict]:
        """Создает крупные блоки из содержания когда структура не найдена"""
        blocks = []
        
        # Разбиваем на крупные блоки по тройным переносам строк
        large_blocks = re.split(r'\n\s*\n\s*\n', content)
        
        for i, block in enumerate(large_blocks):
            block = block.strip()
            if len(block) < 1000:  # Минимум 1000 символов для крупного блока
                continue
                
            # Определяем заголовок из первых строк
            title = self._extract_block_title(block, i, law_name)
            
            blocks.append({
                'type': 'large_block',
                'title': title,
                'content': block,
                'level': 2,
                'size': len(block)
            })
        
        return blocks
    
    def _extract_block_title(self, block: str, index: int, law_name: str) -> str:
        """Извлекает заголовок из блока"""
        lines = block.split('\n')
        if not lines:
            return f"Крупный блок {index + 1} - {law_name}"
        
        # Ищем строку, похожую на заголовок в первых 5 строках
        for i in range(min(5, len(lines))):
            line = lines[i].strip()
            if (50 < len(line) < 200 and 
                not line.endswith('.') and 
                not line.endswith(',') and
                any(c.isupper() for c in line[:50])):
                return line
        
        return f"Раздел {index + 1} - {law_name}"

    def parse_law_enhanced(self, law_file: Path) -> Dict:
        """Улучшенный парсер с поддержкой разных типов структур"""
        
        content = self._read_law_file(law_file)
        if not content:
            return None
        
        # Определяем тип документа
        doc_type = self._get_document_type(law_file.name)
        
        if doc_type == "codes":
            # Стандартный парсер для кодексов
            structures = self.parser.parse_law_major_structures(content, law_file.name)
        else:
            # Новый парсер для простых структур
            structures = self.simple_parser.parse_simple_structure(content, law_file.name)
        
        return {
            'structure': structures,
            'full_content': content,
            'document_type': doc_type
        }
    

class LegalConceptMapper:
    """Маппер юридических концептов на структурные единицы законов"""
    
    def __init__(self):
        self.concept_to_structure = {
            # Гражданское право
            'сделки': {
                'patterns': ['сделк', 'договор', 'обязательств', 'купл', 'продаж'],
                'suggested_structures': ['ГЛАВА 9', 'Раздел III', 'Статья 153']
            },
            'собственность': {
                'patterns': ['собственност', 'имуществ', 'владени', 'правомочи'],
                'suggested_structures': ['ГЛАВА 13', 'Раздел II', 'Статья 209']
            },
            'наследство': {
                'patterns': ['наследств', 'завещан', 'наследник', 'наследовани'],
                'suggested_structures': ['ГЛАВА 61', 'Раздел V', 'Статья 1110']
            },
            
            # Трудовое право
            'трудовой_договор': {
                'patterns': ['трудовой договор', 'трудовые отношения', 'работодатель', 'работник'],
                'suggested_structures': ['ГЛАВА 10', 'ГЛАВА 11', 'Раздел III']
            },
            'увольнение': {
                'patterns': ['увольнен', 'расторжен', 'прекращен', 'трудовой договор'],
                'suggested_structures': ['ГЛАВА 13', 'ГЛАВА 14', 'Статья 77']
            },
            
            # Семейное право
            'брак': {
                'patterns': ['брак', 'супруг', 'заключен', 'расторжен'],
                'suggested_structures': ['ГЛАВА 3', 'ГЛАВА 4', 'Раздел II']
            },
            'алименты': {
                'patterns': ['алимент', 'содержан', 'выплат', 'ребенок'],
                'suggested_structures': ['ГЛАВА 13', 'ГЛАВА 17', 'Раздел V']
            },
            
            # Жилищное право
            'жилье': {
                'patterns': ['жилое помещен', 'квартир', 'дом', 'жилищн'],
                'suggested_structures': ['ГЛАВА 1', 'ГЛАВА 2', 'Раздел I']
            },
            
            # Долевое строительство
            'долевое_строительство': {
                'patterns': ['долев', 'строительств', 'застройщик', 'дольщик'],
                'suggested_structures': ['ГЛАВА 1', 'Раздел I', 'Статья 1']
            }
        }
    
    def find_relevant_structures_for_question(self, question: str) -> List[str]:
        """Находит релевантные структурные единицы для вопроса"""
        question_lower = question.lower()
        relevant_structures = []
        
        for concept, data in self.concept_to_structure.items():
            for pattern in data['patterns']:
                if pattern in question_lower:
                    relevant_structures.extend(data['suggested_structures'])
                    break
        
        return list(set(relevant_structures))  # Убираем дубли

class LawNavigator:
    """Улучшенный навигатор по законам с фокусом на крупные структурные единицы"""
    
    def __init__(self):
        self.config = Config()
        self.project_root = Path(__file__).parent.parent.parent
        self.laws_dir = self.project_root / "laws"
        
        self.parser = EnhancedLawParser()
        self.simple_parser = SimpleLawParser()  # ← ДОБАВИТЬ ЗДЕСЬ
        self.concept_mapper = LegalConceptMapper()
        
        print(f"📚 Инициализация улучшенного LawNavigator...")
        print(f"   Папка законов: {self.laws_dir}")
        print(f"   Существует: {self.laws_dir.exists()}")
        
        self.law_structures = {}
        self._build_law_structures()
    

    def get_sublegal_files(self) -> List[str]:
        """Список файлов подзаконных актов по уже известным структурам."""
        return [
            name
            for name in self.law_structures.keys()
            if self._get_document_type(name) == "sublegal"
        ]

    def get_code_files(self) -> List[str]:
        """Список файлов кодексов."""
        return [
            name
            for name in self.law_structures.keys()
            if self._get_document_type(name) == "codes"
        ]

    def get_plenum_files(self) -> List[str]:
        """Список файлов Пленумов."""
        return [
            name
            for name in self.law_structures.keys()
            if self._get_document_type(name) == "plenums"
        ]

    def _build_law_structures(self):
        """Строит структуры законов с учетом типа документа"""
        print("📚 Анализирую структурные единицы законов...")
        
        if not self.laws_dir.exists():
            print(f"⚠️ Папка {self.laws_dir} не найдена")
            return
        
        for law_file in self.laws_dir.glob("*.txt"):
            try:
                # Читаем файл
                content = self._read_law_file(law_file)
                if not content:
                    print(f"  ❌ Не удалось прочитать {law_file.name}")
                    continue
                
                # Определяем тип документа
                doc_type = self._get_document_type(law_file.name)
                
                # 🔥 ВЫБОР ПАРСЕРА ПО ТИПУ ДОКУМЕНТА
                if doc_type == "codes":
                    # Для кодексов - сложный парсер (крупные структуры)
                    structures = self.parser.parse_law_major_structures(content, law_file.name)
                    type_icon = "🔷"
                elif doc_type == "plenums":
                    # Для Пленумов - специальный парсер из SimpleLawParser
                    structures = self.simple_parser._parse_plenum_by_headings(content, law_file.name)
                    type_icon = "📘"
                elif doc_type == "sublegal":
                    # Для подзаконных актов - парсер статей
                    structures = self.simple_parser._parse_sublegal_structure(content, law_file.name)
                    type_icon = "📋"
                else:
                    # Fallback
                    structures = self.simple_parser.parse_simple_structure(content, law_file.name)
                    type_icon = "🔸"
                
                self.law_structures[law_file.name] = {
                    'structure': structures,
                    'full_content': content,
                    'document_type': doc_type  # Сохраняем тип документа
                }
                
                print(f"  {type_icon} {law_file.name} ({doc_type}): {len(structures)} единиц")
                for structure in structures[:3]:
                    print(f"     └─ {structure['type']}: {structure['title'][:60]}...")
                    
            except Exception as e:
                print(f"  ❌ Ошибка {law_file.name}: {e}")
        
        print(f"📖 Всего проанализировано: {len(self.law_structures)} законов\n")

    def _get_document_type(self, law_file: str) -> str:
        """Определяет тип документа (ПЕРЕНЕСЕН из EnhancedLawParser)"""
        codes = [
            "trudovoy_kodeks.docx", "semeiniy_kodeks.docx", "gk_rf_1.docx", 
            "gk_rf_2.docx", "gk_rf_3.docx", "gk_rf_4.docx", "zhilishniy_kodeks.docx", 
            "koap.docx", "fssp.docx", "pdd.docx", "police.docx", "bankrotstvo.docx", "zpp.docx",
            "Postanov o mkd 354.docx", "Postanov Mos o MKD.docx", "Post pravit N 290.docx"
        ]
        
        # Определяем пленумы по наличию "Plenum" в названии
        plenums = [f.name for f in self.laws_dir.glob("*.txt") if "Plenum" in f.name.lower()]
        
        sublegal = [
            "postanov o neusto k dolevoi.docx", 
            "zakon dolevoi.docx", "Postanov o mrk 491.docx", "Post Gosstoya.docx"
        ]
        
        if law_file in codes:
            return "codes"
        elif law_file in plenums:
            return "plenums"
        elif law_file in sublegal:
            return "sublegal"
        else:
            return "codes"  # по умолчанию

    def _read_law_file(self, law_file: Path) -> str:
        """Читает файл закона. Для .txt - текст, для .docx - извлекает весь текст без структуры (для совместимости)"""
        if law_file.suffix.lower() == '.docx':
            import docx
            try:
                doc = docx.Document(law_file)
                return '\n'.join([para.text for para in doc.paragraphs])
            except Exception as e:
                print(f"Ошибка чтения DOCX {law_file}: {e}")
                return None

        # Для .txt файлов - старая логика
        for encoding in ['utf-8', 'windows-1251', 'cp1251']:
            try:
                with open(law_file, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return None

    
    
    def find_relevant_chapters(self, question: str, law_files: List[str], 
                              max_chapters: int = 5) -> List[Dict]:
        """Поиск релевантных КРУПНЫХ структурных единиц"""
        relevant_structures = []
        
        print(f"   🔍 Поиск КРУПНЫХ структур для: '{question}'")
        
        # 1. Получаем рекомендации от концепт-маппера
        suggested_structures = self.concept_mapper.find_relevant_structures_for_question(question)
        if suggested_structures:
            print(f"   💡 Концепт-маппер рекомендует: {suggested_structures}")
        
        for law_file in law_files:
            if law_file not in self.law_structures:
                continue
            
            law_data = self.law_structures[law_file]
            
            for structure in law_data['structure']:
                relevance = self._calculate_structure_relevance(question, structure, suggested_structures)
                
                if relevance > 0.2:  # Более низкий порог для крупных структур
                    relevant_structures.append({
                        'law': law_file,
                        'title': structure['title'],
                        'content': structure['content'],
                        'relevance': relevance,
                        'type': structure['type'],
                        'size': structure.get('size', 0),
                        'match_type': 'major_structure'
                    })
        
        # Сортируем по релевантности и размеру (крупные структуры получают бонус)
        relevant_structures.sort(key=lambda x: (x['relevance'] * 1.5 + min(x.get('size', 0) / 10000, 0.3)), reverse=True)
        results = relevant_structures[:max_chapters]
        
        print(f"   ✅ Найдено крупных структур: {len(results)}")
        for i, structure in enumerate(results, 1):
            print(f"      {i}. [{structure['type']}] {structure['law']} - {structure['title'][:50]}... (релевантность: {structure['relevance']:.2f})")
        
        return results
    
    def find_relevant_sublegal_articles(self, question: str, max_articles: int = 10) -> List[Dict]:
        """
        Расширенный поиск по подзаконным актам.
        Использует тот же RAG1, но автоматически ограничивается файлами типа 'sublegal'.
        """
        # Берём только подзаконные акты из уже построенных структур
        sublegal_files = self.get_sublegal_files()

        print(f" 🔍 Расширенный поиск по подзаконным актам для: '{question}'")
        print(f" 📂 Будут использоваться файлы: {sublegal_files}")

        # Переиспользуем общий механизм поиска крупных структур
        return self.find_relevant_chapters(
            question=question,
            law_files=sublegal_files,
            max_chapters=max_articles
        )
    
    def _calculate_structure_relevance(self, question: str, structure: Dict, suggested_structures: List[str]) -> float:
        """Вычисляет релевантность крупной структурной единицы"""
        question_lower = question.lower()
        title_lower = structure['title'].lower()
        content_preview = structure['content'][:2000].lower()  # Только превью для крупных структур
        
        score = 0.0
        
        # 1. Проверяем совпадение с рекомендованными структурами
        for suggested in suggested_structures:
            if suggested.lower() in title_lower:
                score += 0.8
                break
        
        # 2. Совпадение ключевых слов в заголовке
        question_words = set(re.findall(r'\b[а-я]{4,}\b', question_lower))
        title_words = set(re.findall(r'\b[а-я]{4,}\b', title_lower))
        
        title_match = len(question_words & title_words)
        score += title_match * 0.3
        
        # 3. Совпадение в содержании (меньший вес для крупных структур)
        content_words = set(re.findall(r'\b[а-я]{4,}\b', content_preview))
        content_match = len(question_words & content_words)
        score += content_match * 0.1
        
        # 4. Бонус за тип структуры (главы и разделы важнее)
        type_bonus = {
            'section': 0.4,
            'chapter': 0.3,
            'subsection': 0.2,
            'major_article': 0.1,
            'large_block': 0.1,
            'article': 0.2,          # статья подзаконного акта
            'preamble': 0.05,        # преамбула подзаконного акта
            'plenum_chapter': 0.25   # глава Пленума
        }
        score += type_bonus.get(structure['type'], 0)
        
        return min(score, 1.0)

    def get_context_for_ai(self, chapters: list, category: str = None, question: str = None) -> dict:
        """Улучшенный контекст для ИИ с акцентом на крупные структуры"""
        if not chapters:
            return {
                'context': "RAG не нашел релевантных КРУПНЫХ структурных единиц для анализа",
                'analysis': "Рекомендуется автономный поиск статей ИИ",
                'priority_laws': [],
                'recommendations': []
            }
        
        # Группируем по типам структур
        structures_by_type = {}
        for chapter in chapters:
            struct_type = chapter.get('type', 'unknown')
            if struct_type not in structures_by_type:
                structures_by_type[struct_type] = []
            structures_by_type[struct_type].append(chapter)
        
        # Форматируем контекст с акцентом на крупные структуры
        context_parts = []
        context_parts.append("🎯 КРУПНЫЕ СТРУКТУРНЫЕ ЕДИНИЦЫ ДЛЯ АНАЛИЗА")
        context_parts.append("=" * 80)
        context_parts.append(f"📂 Категория: {category}")
        context_parts.append(f"❓ Вопрос: {question}")
        context_parts.append(f"📊 Найдено структур: {len(chapters)}")
        context_parts.append("")
        
        # Выводим структуры сгруппированные по типам
        for struct_type, structures in structures_by_type.items():
            type_name = self._get_structure_type_name(struct_type)
            context_parts.append(f"🏛️  {type_name.upper()} ({len(structures)}):")
            context_parts.append("-" * 40)
            
            for i, structure in enumerate(structures, 1):
                relevance = structure.get('relevance', 0)
                relevance_indicator = "🔴" if relevance < 0.3 else "🟡" if relevance < 0.7 else "🟢"
                
                context_parts.append(f"{relevance_indicator} {i}. {structure['law']}")
                context_parts.append(f"   Заголовок: {structure['title']}")
                context_parts.append(f"   Релевантность: {relevance:.2f}")
                context_parts.append(f"   Размер: {structure.get('size', 0)} символов")
                
                # Краткое превью содержания
                content_preview = structure['content'][:300].replace('\n', ' ')
                if len(structure['content']) > 300:
                    content_preview += "..."
                context_parts.append(f"   Превью: {content_preview}")
                context_parts.append("")
        
        context_parts.append("💡 РЕКОМЕНДАЦИИ ДЛЯ ИИ:")
        context_parts.append("-" * 40)
        context_parts.append("1. Анализируйте предложенные КРУПНЫЕ структурные единицы")
        context_parts.append("2. Ищите конкретные статьи внутри этих структур")
        context_parts.append("3. Учитывайте иерархию: Разделы → Главы → Статьи")
        context_parts.append("4. Для точного ответа находите конкретные нормы права")
        
        return {
            'context': "\n".join(context_parts),
            'analysis': f"Найдено {len(chapters)} крупных структурных единиц",
            'priority_laws': list(set(chapter['law'] for chapter in chapters)),
            'recommendations': ["Использовать найденные крупные структуры как основу для поиска конкретных статей"]
        }
    
    def _get_structure_type_name(self, struct_type: str) -> str:
        """Возвращает читаемое название типа структуры"""
        names = {
            'section': 'Раздел',
            'chapter': 'Глава', 
            'subsection': 'Подраздел',
            'major_article': 'Крупная статья',
            'large_block': 'Крупный блок',
            'article': 'Статья подзаконного акта',
            'preamble': 'Преамбула подзаконного акта',
            'plenum_chapter': 'Глава Пленума'
        }
    
        return names.get(struct_type, struct_type)
    # В класс LawNavigator добавляем метод:

    def get_full_chapter_content(self, chapter: Dict) -> str:
        """
        Собирает полный текст главы со всеми дочерними структурными единицами.
        Возвращает объединённый текст всей главы для передачи ИИ.
        """
        law_name = chapter.get('law', '')
        if law_name not in self.law_structures:
            return chapter.get('content', '')
    
        law_data = self.law_structures[law_name]
        chapter_title = chapter.get('title', '')
    
        # Находим все структурные единицы, принадлежащие этой главе
        full_content_parts = [chapter.get('content', '')]
    
        # Ищем дочерние структуры (статьи, параграфы и т.д.)
        for structure in law_data.get('structure', []):
            structure_title = structure.get('title', '')
            structure_content = structure.get('content', '')
        
            # Простая эвристика: если структура следует за главой и до следующей главы,
            # считаем её дочерней (можно улучшить при наличии явных связей)
            if (structure_title and structure_content and 
                structure_title != chapter_title and
                len(structure_content) > 50):  # фильтруем слишком короткие
            
                # Добавляем структуру в общий контент
                full_content_parts.append(f"\n\n{structure_title}\n{structure_content}")
    
        return "\n".join(full_content_parts)