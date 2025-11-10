import os
import pdfplumber
from pathlib import Path
import sys
import math

# Set UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Настройки для разделения документов
MAX_CHARS_PER_PART = 50000  # Максимальное количество символов на часть (можно настроить)
MIN_PARTS = 2  # Минимальное количество частей
MAX_PARTS = 3  # Максимальное количество частей

def split_text_into_parts(text, num_parts):
    """
    Разделяет текст на указанное количество частей, стараясь не разрывать абзацы.
    """
    # Разбиваем текст на абзацы
    paragraphs = text.split('\n\n')
    
    # Если абзацев меньше, чем частей, используем простые разрывы
    if len(paragraphs) < num_parts:
        paragraphs = text.split('\n')
    
    total_chars = len(text)
    chars_per_part = total_chars / num_parts
    
    parts = []
    current_part = ""
    current_chars = 0
    target_chars = chars_per_part
    
    for i, paragraph in enumerate(paragraphs):
        para_chars = len(paragraph)
        
        # Если добавление абзаца не превысит лимит, добавляем его
        if current_chars + para_chars <= target_chars or len(parts) == num_parts - 1:
            if current_part:
                current_part += "\n\n"
            current_part += paragraph
            current_chars += para_chars + 2  # +2 за \n\n
        else:
            # Сохраняем текущую часть и начинаем новую
            if current_part:
                parts.append(current_part.strip())
            current_part = paragraph
            current_chars = para_chars
            target_chars = chars_per_part * (len(parts) + 1)
    
    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part.strip())
    
    return parts

def determine_num_parts(text_length):
    """
    Определяет оптимальное количество частей для документа.
    """
    if text_length <= MAX_CHARS_PER_PART:
        return 1  # Не нужно разделять
    
    # Вычисляем минимальное необходимое количество частей
    min_required = math.ceil(text_length / MAX_CHARS_PER_PART)
    
    # Ограничиваем между MIN_PARTS и MAX_PARTS
    num_parts = max(MIN_PARTS, min(min_required, MAX_PARTS))
    
    return num_parts

pdf_files = list(Path('.').glob('*.pdf'))
output_dir = Path('extracted_texts')
output_dir.mkdir(exist_ok=True)

for pdf_file in pdf_files:
    print(f"\nОбработка: {pdf_file.name}")
    full_text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    full_text += f"\n--- Страница {page_num} ---\n"
                    full_text += text
                    full_text += "\n"
    except Exception as e:
        full_text = f"Ошибка при обработке: {e}"
    
    # Определяем, нужно ли разделять документ
    text_length = len(full_text)
    num_parts = determine_num_parts(text_length)
    
    if num_parts == 1:
        # Сохраняем как один файл
        txt_name = pdf_file.name.replace('.pdf', '.txt')
        output_path = output_dir / txt_name
        with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
            f.write(full_text)
        print(f"  Сохранено: {txt_name} ({text_length} символов)")
    else:
        # Разделяем на части
        print(f"  Документ большой ({text_length} символов), разделяем на {num_parts} части...")
        parts = split_text_into_parts(full_text, num_parts)
        
        base_name = pdf_file.name.replace('.pdf', '')
        for part_num, part_text in enumerate(parts, 1):
            txt_name = f"{base_name}_часть{part_num}_из{num_parts}.txt"
            output_path = output_dir / txt_name
            with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(part_text)
            print(f"  Сохранено: {txt_name} ({len(part_text)} символов)")

print("\n" + "="*60)
print("Извлечение завершено!")
print("="*60)

