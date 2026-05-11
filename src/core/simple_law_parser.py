# src/core/simple_law_parser.py
import re
from typing import List, Dict

class SimpleLawParser:
    """Парсер для документов без сложной структуры (подзаконные акты, Пленумы)"""
    
    def parse_simple_structure(self, content: str, law_name: str) -> List[Dict]:
        structures = []
        
        # Для Пленумов - ищем заголовки глав как отдельные строки
        if "plenum" in law_name.lower() or "postanovlenie" in law_name.lower():
            structures = self._parse_plenum_by_headings(content, law_name)
        # Для подзаконных актов - статьи + пункты
        else:
            structures = self._parse_sublegal_structure(content, law_name)
            
        return structures
    
    def _parse_plenum_by_headings(self, content: str, law_name: str) -> List[Dict]:
        """Улучшенный парсер для Пленумов - ищет реальные структурные единицы"""
        structures = []
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Определяем начало новой структурной единицы в Пленуме
            if self._is_plenum_structure_start(line_clean, i, lines):
                # Сохраняем предыдущую секцию
                if current_section and current_content:
                    structures.append({
                        'type': 'plenum_section',
                        'title': current_section,
                        'content': '\n'.join(current_content),
                        'level': 1,
                        'size': len('\n'.join(current_content))
                    })
                
                # Начинаем новую секцию
                current_section = line_clean
                current_content = [line_clean]
            else:
                # Продолжаем накапливать контент текущей секции
                if current_section:
                    current_content.append(line_clean)
        
        # Добавляем последнюю секцию
        if current_section and current_content:
            structures.append({
                'type': 'plenum_section', 
                'title': current_section,
                'content': '\n'.join(current_content),
                'level': 1,
                'size': len('\n'.join(current_content))
            })
        
        # Если не нашли структур, создаем одну большую
        if not structures:
            structures.append({
                'type': 'plenum_section',
                'title': f"Основные положения - {law_name}",
                'content': content,
                'level': 1,
                'size': len(content)
            })
            
        return structures

    def _is_plenum_structure_start(self, line: str, line_index: int, all_lines: List[str]) -> bool:
        """Определяет начало структурной единицы в Пленуме"""
        
        # Типичные паттерны начала разделов в Пленумах
        plenum_patterns = [
            r'^[IVXLCDM]+\.',                    # Римские цифры: I., II., III.
            r'^\d+\.',                           # Арабские цифры: 1., 2., 3.
            r'^[А-Я][^\.]{5,50}\.$',             # Заголовок с точкой в конце
            r'^[А-Я][^\.]{5,50}:$',              # Заголовок с двоеточием
            r'^(Общие\s+положения|Заключительные\s+положения)', # Конкретные заголовки
            r'^Пункт\s+\d+',                     # Пункт 1, Пункт 2
        ]
        
        for pattern in plenum_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Дополнительные эвристики для Пленумов
        if (len(line) > 20 and len(line) < 150 and 
            line[0].isupper() and 
            not line.endswith((',', ';')) and
            not any(word in line.lower() for word in ['статья', 'глава', 'раздел']) and
            line_index > 0 and all_lines[line_index - 1].strip() == ""):
            return True
        
        return False    
        
    def _is_plenum_chapter_heading(self, line: str, line_index: int, all_lines: List[str]) -> bool:
        """Определяет, является ли строка заголовком главы в Пленуме"""
        
        # Исключаем очевидные не-заголовки
        if len(line) < 5 or len(line) > 200:  # Слишком короткие или длинные
            return False
            
        # Не начинается с цифры, точки, скобки (это скорее пункт)
        if re.match(r'^\d+[\.\)]', line) or re.match(r'^[а-я]\)', line.lower()):
            return False
            
        # Не содержит типичных маркеров статей
        if line.lower().startswith(('статья', 'ст.', 'глава', 'раздел')):
            return True  # Это все-таки может быть заголовком
            
        # Проверяем контекст - перед заголовком часто пустая строка
        has_blank_before = (line_index > 0 and 
                           all_lines[line_index - 1].strip() == "")
        
        # Проверяем форматирование - заголовки часто выделены
        is_uppercase = line.isupper()
        has_typical_heading_words = any(word in line.lower() for word in [
            'общие', 'основные', 'положения', 'порядок', 'правила',
            'особенности', 'заключительные', 'приложение', 'разъяснения'
        ])
        
        # Эвристики для определения заголовка
        heading_indicators = 0
        
        if has_blank_before:
            heading_indicators += 1
        if is_uppercase:
            heading_indicators += 1
        if has_typical_heading_words:
            heading_indicators += 1
        if not line.endswith(('.', ',', ';', ':')):  # Не заканчивается знаками препинания
            heading_indicators += 1
        if len(line.split()) <= 10:  # Не слишком много слов
            heading_indicators += 1
            
        return heading_indicators >= 3  # Если достаточно индикаторов
    
    def _parse_sublegal_structure(self, content: str, law_name: str) -> List[Dict]:
        """Улучшенный парсер для подзаконных актов - статьи + пункты"""
        structures = []
        
        # Ищем все статьи и их содержание
        article_patterns = [
            r'(Статья\s+\d+[\.\s]?)',
            r'(СТАТЬЯ\s+\d+[\.\s]?)',
            r'(ст\.\s*\d+)'
        ]
        
        # Разделяем по статьям
        for pattern in article_patterns:
            articles = re.split(pattern, content)
            if len(articles) > 1:  # Если нашли статьи
                break
        
        # Если не нашли статей по паттернам, пробуем другой подход
        if len(articles) <= 1:
            return self._parse_sublegal_fallback(content, law_name)
        
        # Первый блок - преамбула (если есть)
        preamble = articles[0].strip()
        if preamble and len(preamble) > 50:
            structures.append({
                'type': 'preamble',
                'title': 'Преамбула',
                'content': preamble,
                'level': 0,
                'size': len(preamble)
            })
        
        # Обрабатываем статьи
        for i in range(1, len(articles), 2):
            if i + 1 < len(articles):
                article_title = articles[i].strip()
                article_content = articles[i + 1].strip()
                
                if article_content:
                    structures.append({
                        'type': 'article',
                        'title': article_title,
                        'content': article_content,
                        'level': 1,
                        'size': len(article_content)
                    })
        
        return structures

    def _parse_sublegal_fallback(self, content: str, law_name: str) -> List[Dict]:
        """Fallback парсинг для подзаконных актов без четкой структуры статей"""
        structures = []
        
        # Разбиваем по крупным блокам с нумерацией
        blocks = re.split(r'(\d+\.\s)', content)
        
        if len(blocks) > 1:
            # Первый блок - преамбула
            preamble = blocks[0].strip()
            if preamble and len(preamble) > 50:
                structures.append({
                    'type': 'preamble',
                    'title': 'Преамбула',
                    'content': preamble,
                    'level': 0,
                    'size': len(preamble)
                })
            
            # Обрабатываем нумерованные блоки
            for i in range(1, len(blocks), 2):
                if i + 1 < len(blocks):
                    block_title = f"Пункт {blocks[i].strip()}"
                    block_content = blocks[i + 1].strip()
                    
                    if block_content:
                        structures.append({
                            'type': 'numbered_point',
                            'title': block_title,
                            'content': block_content,
                            'level': 1,
                            'size': len(block_content)
                        })
        
        # Если все еще нет структур, используем общий fallback
        if not structures:
            return self._create_fallback_blocks(content, law_name)
        
        return structures    
        
    def _create_fallback_blocks(self, content: str, law_name: str) -> List[Dict]:
        """Создает блоки когда не удалось распарсить структуру"""
        blocks = []
        
        # Разбиваем по двойным переносам строк
        large_blocks = re.split(r'\n\s*\n', content)
        
        for i, block in enumerate(large_blocks):
            block = block.strip()
            if len(block) < 200:  # Минимум 200 символов
                continue
                
            # Определяем заголовок из первых строк
            title = self._extract_block_title(block, i, law_name)
            
            blocks.append({
                'type': 'large_block',
                'title': title,
                'content': block,
                'level': 1,
                'size': len(block)
            })
        
        return blocks
    
    def _extract_block_title(self, block: str, index: int, law_name: str) -> str:
        """Извлекает заголовок из блока"""
        lines = block.split('\n')
        if not lines:
            return f"Блок {index + 1} - {law_name}"
        
        # Ищем строку, похожую на заголовок в первых 3 строках
        for i in range(min(3, len(lines))):
            line = lines[i].strip()
            if (20 < len(line) < 150 and 
                not line.endswith(('.', ',')) and
                any(c.isupper() for c in line[:30])):
                return line
        
        return f"Раздел {index + 1} - {law_name}"