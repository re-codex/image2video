from __future__ import annotations
from pathlib import Path
from typing import Iterable, Union, Optional, Tuple, Callable, List

import numpy as np
from moviepy import ImageClip, concatenate_videoclips

from .image import fit_to_canvas
from .audio import prepare_audio
from .config import IMAGE_EXTS, AUDIO_EXTS

PathLike = Union[str, Path]
ProgressCB = Optional[Callable[[int, int], None]]


def _collect_images(images: Union[PathLike, Iterable[PathLike]]) -> List[Path]:
    """Собрать все картинки из аргументов: файлы/папки."""
    if isinstance(images, (str, Path)):
        p = Path(images)
        if p.is_dir():
            return sorted(
                x for x in p.iterdir()
                if x.suffix.lower() in IMAGE_EXTS
            )
        elif p.is_file():
            return [p]
        else:
            raise FileNotFoundError(f"Путь не найден: {p}")
    else:
        return [Path(x) for x in images]


def build_video(
    images: Union[PathLike, Iterable[PathLike]],
    out: PathLike,
    sec_per: float,
    fps: int,
    size: Tuple[int, int] = (1080, 1920),
    bg: str = "black",
    audio: Optional[PathLike] = None,
    transitions: bool = False,       # пока не используем, просто принимаем
    audio_adjust: str = "trim",      # "trim" | "loop"
    progress_cb: ProgressCB = None,
) -> str:
    """Основной пайплайн: картинки -> вертикальное видео (+ опционально аудио)."""

    img_paths = _collect_images(images)
    if not img_paths:
        raise ValueError("Нет входных изображений")

    W, H = size

    # старт прогресса
    if progress_cb:
        progress_cb(0, len(img_paths))

    clips: List[ImageClip] = []
    for idx, p in enumerate(img_paths, 1):
        # PIL.Image после вписывания в холст
        frame = fit_to_canvas(p, size=(W, H), bg=bg)

        # в numpy-массив для ImageClip
        frame_arr = np.array(frame)

        clip = ImageClip(frame_arr).with_duration(float(sec_per))
        clips.append(clip)

        if progress_cb:
            progress_cb(idx, len(img_paths))

    # склейка
    video = concatenate_videoclips(clips, method="compose").with_fps(int(fps))

    # аудио (опционально)
    if audio:
        a = prepare_audio(str(audio), target_duration=video.duration, mode=audio_adjust)
        if a is not None:
            video = video.with_audio(a)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    video.write_videofile(
        str(out_path),
        codec="libx264",
        audio_codec="aac",
        fps=int(fps),
    )

    return str(out_path)