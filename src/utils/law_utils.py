# src/utils/law_utils.py
import sys
from pathlib import Path
from typing import List

# Добавляем корень проекта в sys.path для корректного импорта
current_file = Path(__file__)
project_root = current_file.parent.parent.parent  # Поднимаемся на 3 уровня вверх до корня проекта
sys.path.insert(0, str(project_root))

try:
    from config import Config
    print("✅ Модуль config успешно загружен в law_utils.py")
except ImportError as e:
    print(f"❌ Ошибка импорта config в law_utils.py: {e}")
    raise

def get_category_laws(category_id: str, extended: bool = True) -> List[str]:
    """Утилита для получения законов категории (расширенная или базовая версия)"""
    config = Config()
    
    if extended and hasattr(config, 'get_extended_laws_for_category'):
        return config.get_extended_laws_for_category(category_id)
    else:
        # Fallback на старую логику
        if category_id in config.LEGAL_CATEGORIES:
            return config.LEGAL_CATEGORIES[category_id]["laws"]
        return []