"""
CLI интерфейс для Vertical Video Maker
Командная строка для создания видеороликов
"""

import argparse
import sys
import os
import logging
from pathlib import Path
from tqdm import tqdm

# Импорты основного пакета (поддержка относительных и абсолютных импортов)
try:
    from .modules.video_maker import VideoMaker
except ImportError:
    from modules.video_maker import VideoMaker

def setup_logging(verbose: bool = False):
    """Настройка системы логирования"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Форматирование логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(console_handler)
    
    return logger

def validate_arguments(args) -> None:
    """Валидация аргументов командной строки"""
    
    # Проверка существования файлов изображений
    if os.path.isdir(args.images):
        # Если это папка, проверяем что она существует и содержит файлы
        if not os.path.exists(args.images):
            raise FileNotFoundError(f"Папка с изображениями не найдена: {args.images}")
        
        image_extensions = ('.jpg', '.jpeg', '.png')
        if not any(f.lower().endswith(image_extensions) for f in os.listdir(args.images)):
            raise ValueError(f"В папке {args.images} не найдены изображения (.jpg, .png)")
    
    elif os.path.isfile(args.images):
        if not os.path.exists(args.images):
            raise FileNotFoundError(f"Файл изображения не найден: {args.images}")
    else:
        raise ValueError(f"Путь к изображениям не существует: {args.images}")
    
    # Проверка аудиофайла (если указан)
    if args.audio:
        if not os.path.exists(args.audio):
            raise FileNotFoundError(f"Аудиофайл не найден: {args.audio}")
        
        audio_extensions = ('.mp3', '.wav')
        if not args.audio.lower().endswith(audio_extensions):
            raise ValueError(f"Неподдерживаемый формат аудио. Используйте: .mp3, .wav")
    
    # Проверка параметров
    if args.duration <= 0:
        raise ValueError("Длительность кадра должна быть больше 0")
    
    if args.fps not in [24, 30, 60]:
        raise ValueError("FPS должен быть одним из: 24, 30, 60")
    
    if args.width != 1080 or args.height != 1920:
        print("⚠️  Внимание: Рекомендуется использовать разрешение 1080x1920 для вертикальных видео")

def create_progress_callback():
    """Создание callback функции для прогресс-бара"""
    def progress_callback(current_frame, total_frames):
        if hasattr(progress_callback, 'pbar'):
            progress_callback.pbar.update(1)
        else:
            progress_callback.pbar = tqdm(
                total=total_frames, 
                desc="Создание видео", 
                unit="кадр",
                disable=False
            )
    return progress_callback

def main():
    """Основная функция CLI"""
    
    parser = argparse.ArgumentParser(
        description='Vertical Video Maker - Генератор вертикальных видеороликов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --images ./images --audio music.mp3 --output video.mp4
  %(prog)s --images ./images --output video.mp4 --duration 5 --bg-color white
  %(prog)s --images ./images --audio music.mp3 --output video.mp4 --transitions
  
Поддерживаемые форматы:
  Изображения: .jpg, .jpeg, .png
  Аудио: .mp3, .wav
"""
    )
    
    # Основные аргументы
    parser.add_argument(
        '--images', 
        required=True,
        help='Путь к папке с изображениями или к одному изображению'
    )
    
    parser.add_argument(
        '--audio',
        help='Путь к аудиофайлу (опционально)'
    )
    
    parser.add_argument(
        '--output', 
        default='output/video.mp4',
        help='Путь для сохранения видео (по умолчанию: output/video.mp4)'
    )
    
    # Параметры видео
    parser.add_argument(
        '--duration', 
        type=float, 
        default=4.0,
        help='Длительность показа каждого кадра в секундах (по умолчанию: 4.0)'
    )
    
    parser.add_argument(
        '--width', 
        type=int, 
        default=1080,
        help='Ширина видео (по умолчанию: 1080)'
    )
    
    parser.add_argument(
        '--height', 
        type=int, 
        default=1920,
        help='Высота видео (по умолчанию: 1920)'
    )
    
    parser.add_argument(
        '--fps', 
        type=int, 
        default=24,
        choices=[24, 30, 60],
        help='Частота кадров (по умолчанию: 24)'
    )
    
    # Настройки
    parser.add_argument(
        '--bg-color',
        default='black',
        choices=['black', 'white'],
        help='Цвет фона (по умолчанию: black)'
    )
    
    parser.add_argument(
        '--audio-adjust',
        default='trim',
        choices=['trim', 'loop'],
        help='Режим подгонки аудио (по умолчанию: trim)'
    )
    
    parser.add_argument(
        '--transitions',
        action='store_true',
        help='Добавить плавные переходы между кадрами'
    )
    
    # Дополнительные опции
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Показать информацию о входных файлах'
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    logger = setup_logging(args.verbose)
    
    try:
        # Валидация аргументов
        validate_arguments(args)
        
        # Показ информации о файлах
        if args.info:
            print("📁 Информация о входных файлах:")
            
            if os.path.isdir(args.images):
                images = [f for f in os.listdir(args.images) 
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                print(f"   Изображений в папке: {len(images)}")
                if images:
                    print(f"   Первые файлы: {', '.join(images[:3])}")
            else:
                print(f"   Изображение: {os.path.basename(args.images)}")
            
            if args.audio:
                print(f"   Аудио: {os.path.basename(args.audio)}")
            print()
        
        # Создание видео
        video_maker = VideoMaker(
            video_width=args.width,
            video_height=args.height,
            fps=args.fps
        )
        
        print(f"🎬 Создание вертикального видео...")
        print(f"   📐 Разрешение: {args.width}x{args.height}")
        print(f"   🎞️  FPS: {args.fps}")
        print(f"   ⏱️  Длительность кадра: {args.duration}с")
        print(f"   🎨 Фон: {args.bg_color}")
        
        if args.audio:
            print(f"   🎵 Аудио: {args.audio}")
        print()
        
        # Создание видео
        if args.transitions:
            print("✨ Использую переходы между кадрами...")
            output_path = video_maker.create_video_with_custom_transitions(
                image_paths=args.images,
                audio_path=args.audio,
                output_path=args.output,
                frame_duration=args.duration,
                background_color=args.bg_color
            )
        else:
            output_path = video_maker.create_video(
                image_paths=args.images,
                audio_path=args.audio,
                output_path=args.output,
                frame_duration=args.duration,
                background_color=args.bg_color,
                audio_adjust_mode=args.audio_adjust
            )
        
        # Информация о созданном файле
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            
            print("✅ Видео успешно создано!")
            print(f"   📂 Путь: {output_path}")
            print(f"   📏 Размер: {file_size:.1f} MB")
            
            # Информация о видео
            info = video_maker.get_video_info(output_path)
            if 'error' not in info:
                print(f"   ⏱️  Длительность: {info['duration']:.1f}с")
                print(f"   🔊 Аудио: {'Да' if info['audio'] else 'Нет'}")
        else:
            print("❌ Ошибка: файл не создан")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"❌ Ошибка файла: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Ошибка значения: {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"❌ Ошибка зависимости: {e}")
        print("💡 Установите MoviePy: pip install moviepy")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()