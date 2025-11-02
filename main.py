#!/usr/bin/env python3
"""
Vertical Video Maker - Основной модуль
Генератор вертикальных видеороликов из изображений и аудио

Автор: Ваше имя
Версия: 1.0.0
"""

import sys
import logging
from pathlib import Path

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

try:
    from cli import main
except ImportError:
    # Если запускается отдельно
    try:
        from modules.video_maker import VideoMaker
        from modules.image_processor import ImageProcessor
        from modules.audio_processor import AudioProcessor
        
        def main():
            """Fallback функция"""
            print("Vertical Video Maker - Генератор вертикальных видеороликов")
            print("Запустите: python cli.py --help")
        
    except ImportError:
        def main():
            print("❌ Ошибка: Не найдены модули")
            sys.exit(1)

if __name__ == "__main__":
    # Настройка базового логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск CLI
    try:
        main()
    except KeyboardInterrupt:
        print("\\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)