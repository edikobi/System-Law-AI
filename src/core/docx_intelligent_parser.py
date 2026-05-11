import docx
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

# ==========================================
# МОДУЛЬ 1: ИЗВЛЕЧЕНИЕ СТРУКТУРЫ (Structure Extractor)
# ==========================================

def get_xml_outline_level(paragraph) -> Optional[int]:
    """
    [Requirement 1] Извлекает уровень структуры (0, 1, 2...) напрямую из XML.
    Это "источник правды" для файлов из КонсультантПлюс.
    """
    try:
        p_element = paragraph._p
        pPr = p_element.pPr
        if pPr is not None:
            # Ищем тег <w:outlineLvl> в пространстве имен openxmlformats
            outline_lvl = pPr.find(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl"
            )
            if outline_lvl is not None:
                val = outline_lvl.get(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
                )
                return int(val)
    except Exception:
        pass
    return None

# ==========================================
# МОДУЛЬ 2: ПОСТРОИТЕЛЬ ДЕРЕВА (Tree Builder)
# ==========================================

@dataclass
class DocumentNode:
    """Узел дерева документа. Может быть Главой, Параграфом или Статьей."""
    level: int                  # Уровень вложенности (0, 1, 2...)
    title: str                  # Заголовок (напр. "Глава IX")
    content: List[str]          # Собственный текст узла (преамбула)
    children: List['DocumentNode'] = field(default_factory=list) # Вложенные узлы
    parent: Optional['DocumentNode'] = None # Ссылка на родителя (для формирования полного пути)

    @property
    def full_text_size(self) -> int:
        """[Requirement 3] Рекурсивно считает размер текста (своего + всех детей)"""
        own_size = sum(len(p) for p in self.content)
        children_size = sum(child.full_text_size for child in self.children)
        return own_size + children_size

    def get_flat_text(self, include_title: bool = True) -> str:
        """Собирает весь текст поддерева в одну строку (для создания FullChunk)"""
        parts = []
        if include_title and self.title:
            parts.append(self.title)
        parts.extend(self.content)
        for child in self.children:
            parts.append(child.get_flat_text(include_title=True))
        return "\n".join(parts)
    
    def get_breadcrumb_title(self) -> str:
        """Формирует полный путь: 'Глава IX > § 1 > Статья 168'"""
        titles = []
        curr = self
        while curr and curr.level >= 0: # level -1 это фиктивный корень
            if curr.title:
                titles.append(curr.title)
            curr = curr.parent
        return " > ".join(reversed(titles))


class DocxIntelligentParser:
    
    def check_structure_type(self, root_node: DocumentNode) -> str:
        """
        Анализирует построенное дерево и возвращает тип структуры документа.
        
        Возвращает:
        - 'flat': Если в документе нет ни одной структурной единицы (детей).
        - 'simple': Если структура есть, но она примитивная (мало узлов, малая глубина).
        - 'complex': Если это полноценный структурированный документ (Кодекс).
        """
        
        # 1. Проверка на "Плоский" (вообще нет детей)
        if not root_node.children:
            return 'flat'
            
        # 2. Анализ сложности для остальных
        total_nodes = 0
        max_depth = 0
        
        # Простой обход для подсчета статистики
        stack = [(child, 1) for child in root_node.children] # (node, depth)
        
        while stack:
            current, depth = stack.pop()
            total_nodes += 1
            max_depth = max(max_depth, depth)
            
            for child in current.children:
                stack.append((child, depth + 1))
        
        # Критерии "Простоты" (можно настроить)
        # Например: если узлов меньше 5 ИЛИ глубина всего 1 уровень -> Simple
        if total_nodes < 5 or max_depth == 1:
            return 'simple'
            
        return 'complex'
    
    
    def _create_flat_chunk(self, node: DocumentNode) -> List[Dict]:
        """Создает один чанк из всего содержимого узла (рекурсивно)"""
        # Используем get_flat_text, он уже умеет собирать текст рекурсивно
        full_text = node.get_flat_text(include_title=False)
        
        if not full_text.strip():
            return []

        return [{
            "chunk_title": "Полный текст документа",
            "content": full_text,
            "level": 0,
            "size": len(full_text),
            "type": "flat_document",
            "source_node": "ROOT"
        }]    
    
    def parse(self, file_path: str) -> 'DocumentNode':
        """Парсит файл и возвращает КОРНЕВОЙ узел дерева."""
        doc = docx.Document(file_path)
        
        # Фиктивный корень, чтобы собрать все главы верхнего уровня
        root = DocumentNode(level=-1, title="ROOT", content=[])
        
        # [Requirement 2] Стек для отслеживания вложенности
        # stack[-1] - это текущий активный родитель
        stack = [root] 
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text: continue

            # 1. Определяем уровень (XML -> Style -> None)
            lvl = get_xml_outline_level(para)
            
            # Fallback для стилей Heading (на всякий случай)
            if lvl is None and para.style.name.startswith("Heading"):
                try:
                    lvl = int(para.style.name.split()[-1]) - 1
                except:
                    pass

            # 2. Логика построения дерева
            if lvl is not None:
                # ЭТО ЗАГОЛОВОК
                # Поднимаемся по стеку вверх, пока не найдем родителя с уровнем МЕНЬШЕ текущего
                while len(stack) > 1 and stack[-1].level >= lvl:
                    stack.pop()
                
                parent = stack[-1]
                
                # Создаем новый узел
                new_node = DocumentNode(level=lvl, title=text, content=[], parent=parent)
                parent.children.append(new_node)
                
                # Делаем его активным (кладем в стек)
                stack.append(new_node)
            else:
                # ЭТО ОБЫЧНЫЙ ТЕКСТ
                # Добавляем к текущему активному узлу
                stack[-1].content.append(text)
                
        return root

    # ==========================================
    # МОДУЛЬ 3: УМНЫЙ ЧАНКЕР (Smart Chunker)
    # ==========================================

    def chunk_tree(self, node: DocumentNode, max_chars: int = 120000) -> List[Dict]:
        """
        [Requirement 3 & 4] Нарезает дерево на чанки, соблюдая лимит и иерархию.
        """
        chunks = []
        
        # ### НОВОЕ: ПРОВЕРКА НА ПЛОСКИЙ ФАЙЛ (ТОЛЬКО ДЛЯ КОРНЯ) ###
        if node.level == -1:
            # Проверяем тип структуры
            struct_type = self.check_structure_type(node)
            
            # Если файл плоский (нет заголовков вообще) -> Отдаем как один чанк
            if struct_type == 'flat':
                print(f" [INFO] Обнаружен плоский файл (без структуры). Создаю единый чанк.")
                return self._create_flat_chunk(node)
            
            # Если файл "простой" (структура есть, но примитивная) И он маленький
            # Тоже отдаем целиком (опционально, но полезно для вашего Постановления)
            if struct_type == 'simple' and node.full_text_size <= max_chars:
                 print(f" [INFO] Обнаружен простой файл ({node.full_text_size} chars). Создаю единый чанк.")
                 # Для простых файлов используем стандартную логику "влезает целиком", 
                 # но нам нужно принудительно собрать текст рекурсивно, так как node.content пуст у корня
                 # Поэтому просто вызываем helper для плоского чанка, он соберет всё.
                 return self._create_flat_chunk(node)        
        
        # 0. Игнорируем фиктивный корень, сразу идем к детям
        if node.level == -1:
            for child in node.children:
                chunks.extend(self.chunk_tree(child, max_chars))
            return chunks

        # 1. Оценка размера
        total_size = node.full_text_size
        
        # === CASE A: ВЛЕЗАЕТ ЦЕЛИКОМ ===
        if total_size <= max_chars:
            # Создаем один жирный чанк со всем содержимым
            full_content = node.get_flat_text(include_title=False)
            chunks.append({
                "chunk_title": node.get_breadcrumb_title(),

                "source_node_ref": node,  # Ссылка на узел дерева для дальнейшего разбиения
                "content": full_content,
                "level": node.level,
                "size": total_size,
                "type": "full_node",
                "source_node": node.title
            })
            return chunks

        # === CASE B: НЕ ВЛЕЗАЕТ (ДРОБИМ) ===
        print(f"   [INFO] Node '{node.title}' ({total_size} chars) > limit. Splitting...")
        
        # B1. Сохраняем собственный текст узла (введение/преамбула)
        if node.content:
            intro_text = "\n".join(node.content)
            if intro_text.strip():
                chunks.append({
                    "chunk_title": f"{node.get_breadcrumb_title()} (Введение)",
                    "content": intro_text,
                    "level": node.level,
                    "size": len(intro_text),
                    "type": "intro"
                })

        # B2. Обработка детей с ГРУППИРОВКОЙ (Batching)
        current_batch = []
        current_batch_size = 0
        
        for child in node.children:
            child_size = child.full_text_size
            
            # Если сам ребенок жирный (> max_chars), его нельзя батчить. 
            # Сначала сбрасываем накопленный батч, потом обрабатываем гиганта.
            if child_size > max_chars:
                # 1. Сброс батча
                if current_batch:
                    self._flush_batch(chunks, current_batch, node)
                    current_batch = []
                    current_batch_size = 0
                
                # 2. Рекурсивный спуск в гиганта
                chunks.extend(self.chunk_tree(child, max_chars))
                continue
                
            # Если ребенок влезает, пробуем добавить в текущий батч
            if current_batch_size + child_size < max_chars:
                current_batch.append(child)
                current_batch_size += child_size
            else:
                # Батч переполнен -> сохраняем и начинаем новый
                self._flush_batch(chunks, current_batch, node)
                current_batch = [child]
                current_batch_size = child_size
        
        # Сброс остатка
        if current_batch:
            self._flush_batch(chunks, current_batch, node)
            
        return chunks

    def _flush_batch(self, chunks_list, batch: List[DocumentNode], parent: DocumentNode):
        """Вспомогательный метод для сохранения группы мелких детей как одного чанка"""
        if not batch: return
        
        # Формируем заголовок. Если батч из 1 элемента -> его имя. Если много -> диапазон.
        if len(batch) == 1:
            title = batch[0].get_breadcrumb_title()
        else:
            # Пример: "Глава IX > § 1 - § 3"
            start = batch[0].title
            end = batch[-1].title
            title = f"{parent.get_breadcrumb_title()} > {start} ... {end}"
            
        # Собираем контент
        content_parts = []
        for item in batch:
            content_parts.append(item.get_flat_text(include_title=True))
            
        full_text = "\n\n".join(content_parts)
        
        chunks_list.append({
            "chunk_title": title,
            "content": full_text,
            "level": batch[0].level, # Уровень первого элемента
            "size": len(full_text),
            "type": "batched_children"
        })

# ==========================================
# ТОЧКА ВХОДА (Пример использования)
# ==========================================
if __name__ == "__main__":
    # Тест на заглушке или реальном файле
    parser = DocxIntelligentParser()
    
    # Пример вызова (раскомментировать при наличии файла)
    # root = parser.parse("police.docx")
    # chunks = parser.chunk_tree(root, max_chars=10000) # Тестовый лимит
    
    # for c in chunks:
    #     print(f"📦 [{c['type']}] {c['chunk_title']} ({c['size']} chars)")
