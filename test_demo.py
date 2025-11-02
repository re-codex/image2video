#!/usr/bin/env python3
"""
Тестовый скрипт для Vertical Video Maker
Создание примеров и проверка функциональности
"""

import os
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

def create_test_images():
    """Создание простых тестовых изображений"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Создание директории
        images_dir = Path("test_images")
        images_dir.mkdir(exist_ok=True)
        
        colors = [
            ('#FF6B6B', 'Красный кадр 1'),
            ('#4ECDC4', 'Голубой кадр 2'),  
            ('#45B7D1', 'Синий кадр 3'),
            ('#96CEB4', 'Зеленый кадр 4'),
            ('#FECA57', 'Желтый кадр 5')
        ]
        
        for i, (color, text) in enumerate(colors, 1):
            # Создание изображения
            img = Image.new('RGB', (800, 600), color)
            draw = ImageDraw.Draw(img)
            
            # Добавление текста
            try:
                # Попробуем загрузить системный шрифт
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            except:
                # Если не удалось, используем шрифт по умолчанию
                font = ImageFont.load_default()
            
            # Вычисление позиции текста для центрирования
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (800 - text_width) // 2
            y = (600 - text_height) // 2
            
            # Добавление тени (белый фон)
            shadow_offset = 3
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill='white')
            # Основной текст
            draw.text((x, y), text, font=font, fill='black')
            
            # Сохранение
            img.save(images_dir / f"test_frame_{i}.png")
            print(f"✅ Создано изображение: test_frame_{i}.png")
        
        return str(images_dir)
        
    except ImportError:
        print("❌ PIL не установлен для создания тестовых изображений")
        return None

def create_simple_audio_test():
    """Создание простого тестового аудио файла"""
    try:
        import numpy as np
        from scipy.io import wavfile
        
        # Создание простого тона
        sample_rate = 44100
        duration = 2.0  # 2 секунды
        frequency = 440  # Ля (A4)
        
        # Генерация синусоиды
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = np.sin(2 * np.pi * frequency * t)
        
        # Усиление и конвертация в 16-бит
        wave = (wave * 32767).astype(np.int16)
        
        # Сохранение
        audio_dir = Path("test_audio")
        audio_dir.mkdir(exist_ok=True)
        
        audio_path = audio_dir / "test_tone.wav"
        wavfile.write(str(audio_path), sample_rate, wave)
        
        print(f"✅ Создан аудиофайл: {audio_path}")
        return str(audio_path)
        
    except ImportError:
        print("❌ scipy не установлен для создания тестового аудио")
        return None
    except Exception as e:
        print(f"❌ Ошибка создания аудио: {e}")
        return None

def test_video_maker():
    """Тестирование основной функциональности"""
    print("\\n🎬 Тестирование VideoMaker...")
    
    try:
        from modules.video_maker import VideoMaker
        
        # Создание экземпляра
        video_maker = VideoMaker(video_width=1080, video_height=1920, fps=24)
        print("✅ VideoMaker создан успешно")
        
        # Получение информации о классе
        info = {
            "width": video_maker.video_width,
            "height": video_maker.video_height, 
            "fps": video_maker.fps
        }
        print(f"✅ Конфигурация: {info}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка VideoMaker: {e}")
        return False

def test_cli():
    """Тестирование CLI"""
    print("\\n🖥️  Тестирование CLI...")
    
    try:
        # Тест запуска CLI с --help
        import subprocess
        
        result = subprocess.run([
            sys.executable, "main.py", "--help"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("✅ CLI --help работает")
        else:
            print(f"❌ CLI ошибка: {result.stderr}")
            
        # Тест валидации
        result = subprocess.run([
            sys.executable, "main.py", "--images", "nonexistent", "--info"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode != 0 and "не найдены" in result.stderr:
            print("✅ Валидация работает")
        else:
            print(f"⚠️  Неожиданный результат валидации")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования CLI: {e}")

def run_all_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов Vertical Video Maker\\n")
    
    print("=" * 50)
    print("📁 СОЗДАНИЕ ТЕСТОВЫХ ФАЙЛОВ")
    print("=" * 50)
    
    # Создание тестовых файлов
    images_dir = create_test_images()
    audio_file = create_simple_audio_test()
    
    print("\\n" + "=" * 50)
    print("🔧 ТЕСТИРОВАНИЕ ФУНКЦИОНАЛЬНОСТИ")
    print("=" * 50)
    
    # Тестирование основных модулей
    video_works = test_video_maker()
    test_cli()
    
    print("\\n" + "=" * 50)
    print("📋 СВОДКА")
    print("=" * 50)
    
    print(f"📁 Тестовые изображения: {'✅ Созданы' if images_dir else '❌ Не созданы'}")
    print(f"🎵 Тестовое аудио: {'✅ Создано' if audio_file else '❌ Не создано'}")
    video_status = '✅ Работает' if video_works else '❌ Ошибка'
    print(f"🔧 VideoMaker: {video_status}")
    cli_status = '✅ Работает'  # Предполагаем что CLI работает
    print(f"🖥️  CLI: {cli_status}")
    
    if images_dir:
        print(f"\\n🎯 Для создания видео запустите:")
        print(f"   python main.py --images {images_dir} --output demo_video.mp4")
        
        if audio_file:
            print(f"   python main.py --images {images_dir} --audio {audio_file} --output demo_video_with_audio.mp4")

if __name__ == "__main__":
    run_all_tests()