"""
vv — ядро генератора вертикальных видео.
Здесь только константы, версия и верхнеуровневые функции.
"""

from __future__ import annotations

from .config import WIDTH, HEIGHT, FPS, SEC_PER, BG

# Основная публичная точка входа: сборка видео
from .pipeline import build_video


# Версия пакета (подхватывается, когда упакуешь проект)
try:
    from importlib.metadata import version, PackageNotFoundError
    __version__ = version("vertical-video-maker")  # ДОЛЖНО совпасть с [project.name] в pyproject.toml
except Exception:
    __version__ = "0.1.0-dev"

# Удобные алиасы
DEFAULT_SIZE = (WIDTH, HEIGHT)

# Быстрая проверка наличия ffmpeg
def ffmpeg_path() -> str | None:
    import shutil
    return shutil.which("ffmpeg")

__all__ = [
    "build_video", "get_video_info",
    "WIDTH", "HEIGHT", "FPS", "SEC_PER", "BG", "DEFAULT_SIZE",
    "ffmpeg_path", "__version__",
]