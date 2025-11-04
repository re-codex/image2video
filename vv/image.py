from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image, ImageOps
from .config import WIDTH, HEIGHT, BG


def fit_to_canvas(
    path: Path,
    size: Optional[Tuple[int, int]] = None,
    bg: str = BG,
) -> Image.Image:
    """
    Открыть картинку, учесть EXIF-поворот, вписать в холст size
    (по умолчанию 1080x1920) с сохранением пропорций и фоном bg.
    Возвращает PIL.Image.
    """
    if size is None:
        W, H = WIDTH, HEIGHT
    else:
        W, H = size

    im = Image.open(path).convert("RGB")
    im = ImageOps.exif_transpose(im)

    k = min(W / im.width, H / im.height)
    new_w, new_h = int(im.width * k), int(im.height * k)
    im_resized = im.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H), color=bg)
    x = (W - new_w) // 2
    y = (H - new_h) // 2
    canvas.paste(im_resized, (x, y))

    return canvas