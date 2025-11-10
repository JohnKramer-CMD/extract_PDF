import os
import pdfplumber
from pathlib import Path
import sys
import math
import argparse
from typing import List, Tuple
import re

# Set UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Настройки для разделения документов
MAX_CHARS_PER_PART = 50000  # Максимальное количество символов на часть (можно настроить)
MIN_PARTS = 2  # Минимальное количество частей
MAX_PARTS = 3  # Максимальное количество частей

def sanitize_filename(filename: str) -> str:
    """
    Очищает имя файла от недопустимых символов.
    """
    # Удаляем недопустимые символы для Windows/Linux
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Удаляем лишние пробелы
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename

def split_text_into_parts(text: str, num_parts: int) -> List[str]:
    """
    Разделяет текст на указанное количество частей, стараясь не разрывать абзацы.
    """
    if not text.strip():
        return [text]
    
    # Разбиваем текст на абзацы
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    # Если абзацев меньше, чем частей, используем простые разрывы
    if len(paragraphs) < num_parts:
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    
    if len(paragraphs) == 0:
        return [text]
    
    total_chars = len(text)
    chars_per_part = total_chars / num_parts
    
    parts = []
    current_part = ""
    current_chars = 0
    target_chars = chars_per_part
    
    for i, paragraph in enumerate(paragraphs):
        para_chars = len(paragraph)
        
        # Если добавление абзаца не превысит лимит, добавляем его
        # Или если это последняя часть - добавляем все оставшееся
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
    
    # Убеждаемся, что получили нужное количество частей
    if len(parts) < num_parts and len(parts) > 0:
        # Если получилось меньше частей, равномерно распределяем
        while len(parts) < num_parts:
            parts.append("")
    
    return parts[:num_parts]  # Ограничиваем максимальным количеством

def determine_num_parts(text_length: int) -> int:
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

def extract_text_from_pdf(pdf_path: Path) -> Tuple[str, int, str]:
    """
    Извлекает текст из PDF файла.
    Возвращает: (текст, количество страниц, сообщение об ошибке)
    """
    full_text = ""
    total_pages = 0
    error_msg = None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        full_text += f"\n--- Страница {page_num} ---\n"
                        full_text += text
                        full_text += "\n"
                except Exception as e:
                    error_msg = f"Ошибка при извлечении текста со страницы {page_num}: {e}"
                    print(f"  ⚠️  {error_msg}")
            
            if not full_text.strip():
                error_msg = "PDF не содержит текста (возможно, это сканированное изображение)"
                
    except Exception as e:
        error_msg = f"Ошибка при открытии PDF: {e}"
    
    return full_text, total_pages, error_msg

def process_pdf(pdf_file: Path, output_dir: Path, stats: dict) -> None:
    """
    Обрабатывает один PDF файл.
    """
    print(f"\n📄 Обработка: {pdf_file.name}")
    
    full_text, total_pages, error_msg = extract_text_from_pdf(pdf_file)
    
    if error_msg and not full_text.strip():
        print(f"  ❌ {error_msg}")
        stats['errors'] += 1
        return
    
    if not full_text.strip():
        print(f"  ⚠️  Файл пустой или не содержит текста")
        stats['empty'] += 1
        return
    
    # Определяем, нужно ли разделять документ
    text_length = len(full_text)
    num_parts = determine_num_parts(text_length)
    
    # Очищаем имя файла
    base_name = sanitize_filename(pdf_file.stem)
    
    if num_parts == 1:
        # Сохраняем как один файл
        txt_name = f"{base_name}.txt"
        output_path = output_dir / txt_name
        try:
            with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(full_text)
            print(f"  ✅ Сохранено: {txt_name}")
            print(f"     📊 Размер: {text_length:,} символов, {total_pages} страниц")
            stats['processed'] += 1
            stats['total_chars'] += text_length
        except Exception as e:
            print(f"  ❌ Ошибка при сохранении: {e}")
            stats['errors'] += 1
    else:
        # Разделяем на части
        print(f"  📦 Документ большой ({text_length:,} символов), разделяем на {num_parts} части...")
        parts = split_text_into_parts(full_text, num_parts)
        
        saved_parts = 0
        for part_num, part_text in enumerate(parts, 1):
            if not part_text.strip():
                continue
                
            txt_name = f"{base_name}_часть{part_num}_из{num_parts}.txt"
            output_path = output_dir / txt_name
            try:
                with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(part_text)
                print(f"  ✅ Сохранено: {txt_name} ({len(part_text):,} символов)")
                saved_parts += 1
                stats['total_chars'] += len(part_text)
            except Exception as e:
                print(f"  ❌ Ошибка при сохранении части {part_num}: {e}")
        
        if saved_parts > 0:
            stats['processed'] += 1
            stats['split'] += 1
            print(f"     📊 Всего частей: {saved_parts}, {total_pages} страниц")

def main():
    """
    Главная функция программы.
    """
    parser = argparse.ArgumentParser(
        description='Извлечение текста из PDF с автоматическим разделением больших документов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python extract_and_save.py                    # Обработать все PDF в текущей папке
  python extract_and_save.py -d ./pdfs          # Обработать PDF из указанной папки
  python extract_and_save.py -o ./output        # Сохранить в указанную папку
  python extract_and_save.py -r                 # Рекурсивный поиск в подпапках
        """
    )
    
    parser.add_argument(
        '-d', '--directory',
        type=str,
        default='.',
        help='Директория с PDF файлами (по умолчанию: текущая)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='extracted_texts',
        help='Директория для сохранения результатов (по умолчанию: extracted_texts)'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Рекурсивный поиск PDF файлов в подпапках'
    )
    
    parser.add_argument(
        '--max-chars',
        type=int,
        default=MAX_CHARS_PER_PART,
        help=f'Максимальное количество символов на часть (по умолчанию: {MAX_CHARS_PER_PART})'
    )
    
    parser.add_argument(
        '--min-parts',
        type=int,
        default=MIN_PARTS,
        help=f'Минимальное количество частей (по умолчанию: {MIN_PARTS})'
    )
    
    parser.add_argument(
        '--max-parts',
        type=int,
        default=MAX_PARTS,
        help=f'Максимальное количество частей (по умолчанию: {MAX_PARTS})'
    )
    
    args = parser.parse_args()
    
    # Обновляем глобальные настройки из аргументов
    global MAX_CHARS_PER_PART, MIN_PARTS, MAX_PARTS
    MAX_CHARS_PER_PART = args.max_chars
    MIN_PARTS = args.min_parts
    MAX_PARTS = args.max_parts
    
    # Находим PDF файлы
    search_dir = Path(args.directory)
    if not search_dir.exists():
        print(f"❌ Ошибка: директория '{search_dir}' не существует!")
        return 1
    
    if args.recursive:
        pdf_files = list(search_dir.rglob('*.pdf'))
    else:
        pdf_files = list(search_dir.glob('*.pdf'))
    
    if not pdf_files:
        print(f"❌ PDF файлы не найдены в '{search_dir}'")
        return 1
    
    print(f"🔍 Найдено PDF файлов: {len(pdf_files)}")
    
    # Создаем выходную директорию
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Результаты будут сохранены в: {output_dir.absolute()}")
    
    # Статистика обработки
    stats = {
        'processed': 0,
        'errors': 0,
        'empty': 0,
        'split': 0,
        'total_chars': 0
    }
    
    # Обрабатываем каждый PDF
    for pdf_file in pdf_files:
        process_pdf(pdf_file, output_dir, stats)
    
    # Выводим итоговую статистику
    print("\n" + "="*60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*60)
    print(f"✅ Успешно обработано: {stats['processed']}")
    if stats['split'] > 0:
        print(f"📦 Разделено на части: {stats['split']}")
    if stats['empty'] > 0:
        print(f"⚠️  Пустых файлов: {stats['empty']}")
    if stats['errors'] > 0:
        print(f"❌ Ошибок: {stats['errors']}")
    print(f"📝 Всего символов извлечено: {stats['total_chars']:,}")
    print("="*60)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
