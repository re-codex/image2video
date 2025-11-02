"""
Модуль обработки изображений
Загрузка, масштабирование и подготовка изображений для вертикального видео
"""

import os
from typing import List, Union
from PIL import Image, ImageOps
import logging

class ImageProcessor:
    """
    Класс для обработки изображений перед созданием видео
    Поддерживает форматы .jpg и .png
    """
    
    def __init__(self, width: int = 1080, height: int = 1920):
        """
        Инициализация процессора изображений
        
        Args:
            width: Ширина целевого видео (по умолчанию 1080)
            height: Высота целевого видео (по умолчанию 1920)
        """
        self.width = width
        self.height = height
        self.logger = logging.getLogger(__name__)
        
    def load_images(self, image_paths: Union[str, List[str]]) -> List[str]:
        """
        Загрузка изображений из путей
        
        Args:
            image_paths: Путь к папке или список путей к файлам
            
        Returns:
            Список путей к валидным изображениям
            
        Raises:
            FileNotFoundError: Если файлы не найдены
            ValueError: Если неподдерживаемый формат
        """
        valid_images = []
        
        if isinstance(image_paths, str):
            # Если это папка
            if os.path.isdir(image_paths):
                for filename in os.listdir(image_paths):
                    filepath = os.path.join(image_paths, filename)
                    if self._is_valid_image(filepath):
                        valid_images.append(filepath)
            # Если это один файл
            elif os.path.isfile(image_paths):
                if self._is_valid_image(image_paths):
                    valid_images.append(image_paths)
                else:
                    raise ValueError(f"Неподдерживаемый формат файла: {image_paths}")
            else:
                raise FileNotFoundError(f"Путь не существует: {image_paths}")
        
        elif isinstance(image_paths, list):
            for path in image_paths:
                if os.path.isfile(path) and self._is_valid_image(path):
                    valid_images.append(path)
                elif os.path.isfile(path):
                    self.logger.warning(f"Неподдерживаемый формат: {path}")
        
        if not valid_images:
            raise FileNotFoundError("Не найдено валидных изображений")
            
        self.logger.info(f"Загружено {len(valid_images)} изображений")
        return sorted(valid_images)
    
    def _is_valid_image(self, filepath: str) -> bool:
        """Проверка валидности изображения"""
        try:
            with Image.open(filepath) as img:
                format_lower = img.format.lower() if img.format else ""
                return format_lower in ['jpeg', 'jpg', 'png']
        except Exception:
            return False
    
    def process_image(self, image_path: str, background_color: str = 'black') -> Image.Image:
        """
        Обработка одного изображения
        
        Args:
            image_path: Путь к изображению
            background_color: Цвет фона (black, white или hex)
            
        Returns:
            PIL.Image обработанное изображение
        """
        with Image.open(image_path) as img:
            # Конвертация в RGB если необходимо
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Вычисление размеров для сохранения пропорций
            img_width, img_height = img.size
            aspect_ratio = img_width / img_height
            
            target_ratio = self.width / self.height
            
            if aspect_ratio > target_ratio:
                # Изображение шире - масштабируем по ширине
                new_width = self.width
                new_height = int(self.width / aspect_ratio)
            else:
                # Изображение выше - масштабируем по высоте
                new_height = self.height
                new_width = int(self.height * aspect_ratio)
            
            # Масштабирование изображения
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Создание фона
            if background_color == 'black':
                background = Image.new('RGB', (self.width, self.height), (0, 0, 0))
            elif background_color == 'white':
                background = Image.new('RGB', (self.width, self.height), (255, 255, 255))
            else:
                # Hex цвет
                background = Image.new('RGB', (self.width, self.height), background_color)
            
            # Центрирование изображения на фоне
            x_offset = (self.width - new_width) // 2
            y_offset = (self.height - new_height) // 2
            
            background.paste(resized_img, (x_offset, y_offset))
            
            self.logger.debug(f"Обработано изображение: {os.path.basename(image_path)}")
            return background
    
    def process_multiple_images(self, image_paths: List[str], 
                              background_color: str = 'black') -> List[Image.Image]:
        """
        Обработка нескольких изображений
        
        Args:
            image_paths: Список путей к изображениям
            background_color: Цвет фона
            
        Returns:
            Список обработанных изображений
        """
        processed_images = []
        
        for path in image_paths:
            try:
                processed_img = self.process_image(path, background_color)
                processed_images.append(processed_img)
            except Exception as e:
                self.logger.error(f"Ошибка обработки {path}: {e}")
                continue
        
        return processed_images
    
    def save_processed_images(self, images: List[Image.Image], output_dir: str) -> List[str]:
        """
        Сохранение обработанных изображений
        
        Args:
            images: Список обработанных изображений
            output_dir: Директория для сохранения
            
        Returns:
            Список путей к сохраненным файлам
        """
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        
        for i, img in enumerate(images):
            output_path = os.path.join(output_dir, f"processed_frame_{i:03d}.jpg")
            img.save(output_path, quality=95)
            saved_paths.append(output_path)
        
        self.logger.info(f"Сохранено {len(saved_paths)} обработанных изображений в {output_dir}")
        return saved_paths