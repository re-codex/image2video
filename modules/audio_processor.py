"""
Модуль обработки аудио
Загрузка и подготовка аудиофайлов для видео
"""

import os
from typing import Union, Optional
import logging

try:
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    from moviepy.audio.io import AudioArrayClip
    import numpy as np
except ImportError as e:
    logging.warning(f"MoviePy не установлен: {e}")
    MoviePy_available = False
else:
    MoviePy_available = True

class AudioProcessor:
    """
    Класс для обработки аудиофайлов
    Поддерживает MP3 и WAV форматы
    """
    
    def __init__(self):
        """Инициализация процессора аудио"""
        self.logger = logging.getLogger(__name__)
        self.audio_clip = None
        
    def load_audio(self, audio_path: str) -> 'AudioFileClip':
        """
        Загрузка аудиофайла
        
        Args:
            audio_path: Путь к аудиофайлу
            
        Returns:
            AudioFileClip объект
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если неподдерживаемый формат
        """
        if not MoviePy_available:
            raise ImportError("MoviePy необходим для работы с аудио")
            
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")
        
        # Проверка формата
        format_lower = os.path.splitext(audio_path)[1].lower()
        if format_lower not in ['.mp3', '.wav']:
            raise ValueError(f"Неподдерживаемый формат: {format_lower}. Поддерживаются: .mp3, .wav")
        
        try:
            self.audio_clip = AudioFileClip(audio_path)
            self.logger.info(f"Загружен аудиофайл: {os.path.basename(audio_path)}")
            return self.audio_clip
        except Exception as e:
            self.logger.error(f"Ошибка загрузки аудио {audio_path}: {e}")
            raise
    
    def adjust_duration(self, target_duration: float, 
                       adjust_mode: str = 'trim') -> 'AudioFileClip':
        """
        Подгонка длительности аудио под цель
        
        Args:
            target_duration: Целевая длительность в секундах
            adjust_mode: Режим подгонки ('trim' - обрезка, 'loop' - зацикливание)
            
        Returns:
            AudioFileClip с подогнанной длительностью
        """
        if self.audio_clip is None:
            raise ValueError("Аудио не загружено. Сначала вызовите load_audio()")
        
        current_duration = self.audio_clip.duration
        
        if adjust_mode == 'trim':
            # Обрезка аудио
            if current_duration > target_duration:
                adjusted_clip = self.audio_clip.subclip(0, target_duration)
            else:
                # Если аудио короче - используем как есть
                adjusted_clip = self.audio_clip
                
        elif adjust_mode == 'loop':
            # Зацикливание аудио
            if current_duration == 0:
                raise ValueError("Нельзя зацикливать пустое аудио")
            
            # Вычисляем количество повторов
            num_loops = int(target_duration / current_duration) + 1
            audio_array = self.audio_clip.to_soundarray()
            
            # Создаем зацикленный массив
            looped_array = np.tile(audio_array, (num_loops, 1))
            
            # Обрезаем до целевой длительности
            target_samples = int(target_duration * self.audio_clip.fps)
            looped_array = looped_array[:target_samples]
            
            adjusted_clip = AudioArrayClip(looped_array, fps=self.audio_clip.fps)
            
        else:
            raise ValueError(f"Неизвестный режим подгонки: {adjust_mode}. Используйте 'trim' или 'loop'")
        
        self.logger.info(f"Длительность аудио подогнана: {adjusted_clip.duration:.2f}с")
        return adjusted_clip
    
    def normalize_audio(self, target_level: float = 0.8) -> 'AudioFileClip':
        """
        Нормализация уровня громкости аудио
        
        Args:
            target_level: Целевой уровень громкости (0.0-1.0)
            
        Returns:
            AudioFileClip с нормализованной громкостью
        """
        if self.audio_clip is None:
            raise ValueError("Аудио не загружено")
        
        # Преобразуем в массив для обработки
        audio_array = self.audio_clip.to_soundarray()
        
        # Находим максимальное значение
        max_val = np.max(np.abs(audio_array))
        
        if max_val > 0:
            # Нормализуем
            normalized_array = audio_array * (target_level / max_val)
            normalized_clip = AudioArrayClip(normalized_array, fps=self.audio_clip.fps)
            self.logger.info("Аудио нормализовано")
        else:
            normalized_clip = self.audio_clip
        
        return normalized_clip
    
    def add_fade(self, fade_in_duration: float = 0.5, 
                fade_out_duration: float = 0.5) -> 'AudioFileClip':
        """
        Добавление fade-in и fade-out эффектов
        
        Args:
            fade_in_duration: Длительность fade-in в секундах
            fade_out_duration: Длительность fade-out в секундах
            
        Returns:
            AudioFileClip с fade эффектами
        """
        if self.audio_clip is None:
            raise ValueError("Аудио не загружено")
        
        faded_clip = self.audio_clip.fadein(fade_in_duration).fadeout(fade_out_duration)
        self.logger.info(f"Добавлены fade эффекты: in={fade_in_duration}с, out={fade_out_duration}с")
        return faded_clip
    
    def get_audio_info(self) -> dict:
        """
        Получение информации об аудиофайле
        
        Returns:
            Словарь с информацией об аудио
        """
        if self.audio_clip is None:
            return {"error": "Аудио не загружено"}
        
        return {
            "duration": self.audio_clip.duration,
            "fps": self.audio_clip.fps,
            "channels": self.audio_clip.nchannels,
            "size": len(self.audio_clip.to_soundarray()) if self.audio_clip.to_soundarray() is not None else 0
        }
    
    def cleanup(self):
        """Очистка ресурсов"""
        if self.audio_clip is not None:
            self.audio_clip.close()
            self.logger.info("Ресурсы аудио очищены")