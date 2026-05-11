import os
import json
import time
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импортов
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Импортируем ВАШИ существующие инструменты
from src.core.law_navigator import EnhancedLawParser
from src.core.sequential_searcher import IntelligentChunkManager
from config import Config

def main():
    print("🚀 ЗАПУСК ПРЕДВАРИТЕЛЬНОЙ ПОДГОТОВКИ ЗАКОНОВ (PRE-CHUNKING)")
    
    # 1. Настройка путей
    laws_dir = PROJECT_ROOT / "laws"
    processed_dir = PROJECT_ROOT / "processed_laws"
    processed_dir.mkdir(exist_ok=True)
    
    # 2. Инициализация компонентов (используем те же классы, что и в живом поиске)
    # EnhancedLawParser сам решит, использовать DocxLawParser или SimpleLawParser
    navigator_parser = EnhancedLawParser() 
    # IntelligentChunkManager нарежет крупные главы на подчанки для LLM
    chunk_manager = IntelligentChunkManager()
    
    # 3. Получаем список файлов
    law_files = sorted(
        [p for p in laws_dir.glob("*.txt")] + 
        [p for p in laws_dir.glob("*.docx")]
    )
    
    if not law_files:
        print("⚠️ В папке 'laws' нет файлов .txt или .docx")
        return

    print(f"📚 Найдено файлов законов: {len(law_files)}")
    
    # 4. Обработка
    for i, law_path in enumerate(law_files, 1):
        law_name = law_path.name
        print(f"\n[{i}/{len(law_files)}] Обработка: {law_name}")
        start_time = time.time()
        
        try:
            # --- ЭТАП 1: ПАРСИНГ СТРУКТУРЫ (как в LawNavigator) ---
            # Читаем контент (для txt нужен текст, для docx парсер сам откроет файл по пути)
            content = ""
            if law_name.endswith('.txt'):
                # Читаем с учетом кодировок (как в _read_law_file)
                for enc in ['utf-8', 'windows-1251', 'cp1251']:
                    try:
                        with open(law_path, 'r', encoding=enc) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
            
            # Вызываем EnhancedLawParser. Он внутри себя вызовет DocxLawParser для .docx
            # и вернет список "крупных структур" (глав/разделов)
            major_structures = navigator_parser.parse_law_major_structures(content, law_name)
            
            if not major_structures:
                print(f"   ⚠️ Не удалось извлечь структуры. Пропускаем.")
                continue
                
            print(f"   -> Извлечено крупных структур (глав/разделов): {len(major_structures)}")

            # --- ЭТАП 2: НАРЕЗКА НА ЧАНКИ (как в SequentialSearcher) ---
            final_units = []
            
            for structure in major_structures:
                # Важно: добавляем имя закона, если его нет (нужно для searcher'а)
                structure['law'] = law_name
                
                # IntelligentChunkManager берет структуру и разбивает её, если она большая
                # Возвращает список готовых словарей с 'type', 'content', 'title'
                units = chunk_manager.prepare_chapter_analysis(structure)
                final_units.extend(units)

            # --- ЭТАП 3: СОХРАНЕНИЕ ---
            output_data = {
                "law": law_name,
                "processed_at": time.time(),
                "total_units": len(final_units),
                "source_parser": "EnhancedLawParser + DocxLawParser",
                "units": final_units 
            }
            
            output_path = processed_dir / f"{law_name}.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                
            elapsed = time.time() - start_time
            print(f"   ✅ Готово! Сохранено {len(final_units)} поисковых юнитов ({elapsed:.2f}с)")

        except Exception as e:
            print(f"   ❌ Критическая ошибка при обработке {law_name}: {e}")
            # Важно: не останавливаем весь процесс из-за одного битого файла

    print("\n🎉 Вся индексация завершена!")

if __name__ == "__main__":
    main()
