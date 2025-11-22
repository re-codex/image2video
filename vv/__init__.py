"""
vv — ядро генератора вертикальных видео.
Здесь только константы, версия и верхнеуровневые функции.
"""

from __future__ import annotations

from .config import WIDTH, HEIGHT, FPS, SEC_PER, BG
from .pipeline import build_video

# Версия пакета (пока просто константа;
# если будешь упаковывать — заменим на importlib.metadata.version)
__version__ = "0.1.0-dev"

# Удобный алиас
DEFAULT_SIZE = (WIDTH, HEIGHT)

def ffmpeg_path() -> str | None:
    """Вернёт путь до ffmpeg, если он есть в PATH, иначе None."""
    import shutil
    return shutil.which("ffmpeg")

__all__ = [
    "build_video",
    "WIDTH", "HEIGHT", "FPS", "SEC_PER", "BG", "DEFAULT_SIZE",
    "ffmpeg_path", "__version__",
]