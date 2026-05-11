from docx import Document

def inspect_docx_structure(file_path):
    print(f"🔍 Анализ структуры файла: {file_path}")
    doc = Document(file_path)
    
    # Смотрим первые 50 параграфов, чтобы понять структуру
    for i, para in enumerate(doc.paragraphs[:50]):
        # Пропускаем пустые строки
        if not para.text.strip():
            continue
            
        # Выводим: Текст (обрезанный) || Название стиля
        print(f"Строка {i}: [{para.style.name}] -> {para.text[:60]}...")

# Пример использования:
# inspect_docx_structure("law_test.docx")
