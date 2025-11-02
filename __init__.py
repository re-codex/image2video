"""
Vertical Video Maker - основной пакет
Генератор вертикальных видеороликов из изображений и аудио
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .modules.video_maker import VideoMaker
from .modules.image_processor import ImageProcessor  
from .modules.audio_processor import AudioProcessor

__all__ = ["VideoMaker", "ImageProcessor", "AudioProcessor"]