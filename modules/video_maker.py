"""
Основной модуль создания видео
Объединение изображений и аудио в вертикальный видеоролик
"""

import os
import logging
from typing import List, Union, Optional
from pathlib import Path

try:
    from moviepy.editor import (
        ImageClip, VideoFileClip, concatenate_videoclips, 
        CompositeVideoClip, ColorClip
    )
    MoviePy_available = True
except ImportError:
    logging.warning("MoviePy не установлен")
    MoviePy_available = False

try:
    from .image_processor import ImageProcessor
    from .audio_processor import AudioProcessor
except ImportError:
    from image_processor import ImageProcessor
    from audio_processor import AudioProcessor

class VideoMaker:
    """
    Основной класс для создания вертикальных видеороликов
    """
    
    def __init__(self, video_width: int = 1080, video_height: int = 1920, fps: int = 24):
        """
        Инициализация генератора видео
        
        Args:
            video_width: Ширина видео (по умолчанию 1080)
            video_height: Высота видео (по умолчанию 1920)
            fps: Частота кадров (по умолчанию 24)
        """
        if not MoviePy_available:
            raise ImportError("MoviePy необходим для создания видео")
        
        self.video_width = video_width
        self.video_height = video_height
        self.fps = fps
        self.logger = logging.getLogger(__name__)
        
        # Инициализация процессоров
        self.image_processor = ImageProcessor(video_width, video_height)
        self.audio_processor = AudioProcessor()
    
    def create_video(self, 
                    image_paths: Union[str, List[str]],
                    audio_path: Optional[str] = None,
                    output_path: str = "output/video.mp4",
                    frame_duration: float = 4.0,
                    background_color: str = 'black',
                    audio_adjust_mode: str = 'trim') -> str:
        """
        Создание видеоролика из изображений и аудио
        
        Args:
            image_paths: Путь к папке или список путей к изображениям
            audio_path: Путь к аудиофайлу (опционально)
            output_path: Путь для сохранения видео
            frame_duration: Длительность показа каждого кадра (секунды)
            background_color: Цвет фона (black, white или hex)
            audio_adjust_mode: Режим подгонки аудио ('trim' или 'loop')
            
        Returns:
            Путь к созданному видеофайлу
            
        Raises:
            Exception: При ошибке создания видео
        """
        try:
            # Создание директории для вывода
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            # Создание временной директории для кадров
            temp_dir = os.path.join(os.path.dirname(output_path), "temp_frames")
            os.makedirs(temp_dir, exist_ok=True)
            
            self.logger.info("Начинаю создание видео...")
            
            # Загрузка и обработка изображений
            self.logger.info("Обработка изображений...")
            image_paths = self.image_processor.load_images(image_paths)
            processed_images = self.image_processor.process_multiple_images(
                image_paths, background_color
            )
            
            # Создание временных файлов для изображений
            temp_image_paths = []
            for i, img in enumerate(processed_images):
                temp_path = os.path.join(temp_dir, f"frame_{i:03d}.jpg")
                img.save(temp_path, quality=95)
                temp_image_paths.append(temp_path)
            
            # Создание видеоклипов из временных файлов
            self.logger.info("Создание видеоклипов...")
            video_clips = []
            total_duration = 0
            
            for i, temp_path in enumerate(temp_image_paths):
                # Создание ImageClip с заданной длительностью
                clip = ImageClip(temp_path).set_duration(frame_duration)
                video_clips.append(clip)
                total_duration += frame_duration
                self.logger.debug(f"Создан кадр {i+1}/{len(temp_image_paths)}: {frame_duration}с")
            
            # Объединение видеоклипов
            self.logger.info("Объединение видеоклипов...")
            final_video = concatenate_videoclips(video_clips, method="compose")
            
            # Добавление аудио если есть
            if audio_path:
                self.logger.info("Обработка аудио...")
                audio_clip = self.audio_processor.load_audio(audio_path)
                
                # Подгонка аудио под длительность видео
                adjusted_audio = self.audio_processor.adjust_duration(
                    total_duration, audio_adjust_mode
                )
                
                # Добавление fade эффектов
                if total_duration > 1.0:  # Только если видео достаточно длинное
                    adjusted_audio = self.audio_processor.add_fade(0.5, 0.5)
                
                # Нормализация громкости
                adjusted_audio = self.audio_processor.normalize_audio()
                
                # Добавление аудио к видео
                final_video = final_video.set_audio(adjusted_audio)
                self.logger.info(f"Аудио добавлено: {audio_path}")
            
            # Экспорт видео
            self.logger.info(f"Экспорт видео в {output_path}...")
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                logger=None  # Отключаем логирование MoviePy для чистоты вывода
            )
            
            # Очистка ресурсов
            self.logger.info("Очистка ресурсов...")
            final_video.close()
            for clip in video_clips:
                clip.close()
            if audio_path:
                self.audio_processor.cleanup()
            
            # Очистка временных файлов
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                self.logger.debug("Временные файлы удалены")
            
            self.logger.info(f"Видео успешно создано: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Ошибка создания видео: {e}")
            raise
    
    def create_video_with_custom_transitions(self,
                                           image_paths: Union[str, List[str]],
                                           audio_path: Optional[str] = None,
                                           output_path: str = "output/video.mp4",
                                           frame_duration: float = 4.0,
                                           transition_duration: float = 0.5,
                                           background_color: str = 'black') -> str:
        """
        Создание видео с переходами между кадрами
        
        Args:
            image_paths: Пути к изображениям
            audio_path: Путь к аудио
            output_path: Путь для сохранения
            frame_duration: Длительность показа каждого кадра
            transition_duration: Длительность перехода
            background_color: Цвет фона
            
        Returns:
            Путь к созданному видео
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            self.logger.info("Создание видео с переходами...")
            
            # Загрузка изображений
            image_paths = self.image_processor.load_images(image_paths)
            processed_images = self.image_processor.process_multiple_images(
                image_paths, background_color
            )
            
            # Создание клипов с переходами
            clips = []
            
            for i, img in enumerate(processed_images):
                clip = ImageClip(img)
                
                # Устанавливаем время начала клипа
                start_time = i * frame_duration
                end_time = start_time + frame_duration
                
                # Добавляем fade эффекты (если это не первый или последний клип)
                if i == 0:
                    # Первый клип - только fade out
                    clip = clip.fadeout(transition_duration)
                elif i == len(processed_images) - 1:
                    # Последний клип - только fade in
                    clip = clip.fadein(transition_duration)
                else:
                    # Средние клипы - оба эффекта
                    clip = clip.fadein(transition_duration).fadeout(transition_duration)
                    start_time += transition_duration / 2
                    end_time -= transition_duration / 2
                
                clip = clip.set_start(start_time).set_duration(end_time - start_time)
                clips.append(clip)
            
            # Объединение клипов
            final_video = CompositeVideoClip(clips)
            total_duration = len(processed_images) * frame_duration
            
            # Добавление аудио
            if audio_path:
                audio_clip = self.audio_processor.load_audio(audio_path)
                adjusted_audio = self.audio_processor.adjust_duration(total_duration, 'trim')
                final_video = final_video.set_audio(adjusted_audio)
            
            # Экспорт
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio_codec='aac',
                logger=None
            )
            
            # Очистка
            final_video.close()
            for clip in clips:
                clip.close()
            if audio_path:
                self.audio_processor.cleanup()
            
            self.logger.info(f"Видео с переходами создано: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Ошибка создания видео с переходами: {e}")
            raise
    
    def get_video_info(self, video_path: str) -> dict:
        """
        Получение информации о созданном видео
        
        Args:
            video_path: Путь к видеофайлу
            
        Returns:
            Словарь с информацией о видео
        """
        try:
            video = VideoFileClip(video_path)
            info = {
                "path": video_path,
                "duration": video.duration,
                "fps": video.fps,
                "size": (video.w, video.h),
                "audio": video.audio is not None
            }
            video.close()
            return info
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о видео: {e}")
            return {"error": str(e)}