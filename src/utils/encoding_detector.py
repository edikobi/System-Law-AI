# src/utils/encoding_detector.py
import chardet
from pathlib import Path

def detect_encoding(file_path: Path) -> str:
    """Определяет кодировку файла"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']
    
    print(f"   🔍 Кодировка {file_path.name}: {encoding} (уверенность: {confidence:.2f})")
    
    # Если уверенность низкая или кодировка None, используем Windows-1251 как fallback
    if encoding is None or confidence < 0.7:
        return 'windows-1251'
    
    return encoding

def read_file_with_encoding(file_path: Path) -> str:
    """Читает файл с автоматическим определением кодировки"""
    try:
        encoding = detect_encoding(file_path)
        
        # Пробуем прочитать с определенной кодировкой
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        return content
        
    except UnicodeDecodeError:
        # Если не получилось, пробуем альтернативные кодировки
        encodings_to_try = ['utf-8', 'windows-1251', 'cp866', 'iso-8859-5', 'koi8-r']
        
        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"   ✅ Успешно прочитан с кодировкой: {encoding}")
                return content
            except UnicodeDecodeError:
                continue
        
        # Если ничего не помогло, используем utf-8 с игнорированием ошибок
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        print(f"   ⚠️  Прочитан с игнорированием ошибок кодировки")
        return content