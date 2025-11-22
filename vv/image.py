from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from .config import WIDTH, HEIGHT, BG

PathLike = str | Path


def fit_to_canvas(
    path: PathLike,
    size: tuple[int, int] | None = None,
    bg: str = BG,
    mode: str = "fit",   # "fit" | "cover"
    fancy_bg: bool = True,  # размазанный фон из самой картинки
    offset: tuple[float, float] | None = None,  # для "cover": (ox, oy) в диапазоне [-1, 1]
) -> Image.Image:
    """
    Открыть картинку, учесть EXIF-поворот и вписать в вертикальный холст.

    mode="fit"   — вписать целиком, сохранить пропорции, добавить фон (цветной или размытую копию).
    mode="cover" — заполнить весь кадр, лишнее обрезать (кроп); offset задаёт сдвиг окна кадрирования:
                   (-1, -1) — максимально влево/вверх, (0, 0) — центр, (1, 1) — вправо/вниз.
    """
    if size is None:
        W, H = WIDTH, HEIGHT
    else:
        W, H = size

    im = Image.open(path).convert("RGB")
    im = ImageOps.exif_transpose(im)

    if mode == "cover":
        # масштабируем так, чтобы кадр полностью заполнился, лишнее обрежется
        k = max(W / im.width, H / im.height)
        new_w, new_h = int(im.width * k), int(im.height * k)
        im_resized = im.resize((new_w, new_h), Image.LANCZOS)

        # сколько "лишнего" по краям
        extra_x = max(0, new_w - W)
        extra_y = max(0, new_h - H)

        # offset в [-1, 1] → позиция окна в диапазоне [0, extra]
        if offset is None:
            ox, oy = 0.0, 0.0
        else:
            ox, oy = offset

        ox = float(max(-1.0, min(1.0, ox)))
        oy = float(max(-1.0, min(1.0, oy)))

        # -1 → 0 (левый край), 0 → середина, 1 → правый край
        tx = (ox + 1.0) / 2.0
        ty = (oy + 1.0) / 2.0

        left = int(round(extra_x * tx))
        top = int(round(extra_y * ty))
        right = left + W
        bottom = top + H

        return im_resized.crop((left, top, right, bottom))

    elif mode == "fit":
        # вписываем целиком, но фон может быть либо однотонным, либо fancy
        k = min(W / im.width, H / im.height)
        new_w, new_h = int(im.width * k), int(im.height * k)
        im_resized = im.resize((new_w, new_h), Image.LANCZOS)

        if fancy_bg:
            # фон из самой картинки: растянули, размыли, затемнили
            bg_img = im.resize((W, H), Image.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=30))
            bg_img = ImageEnhance.Brightness(bg_img).enhance(0.5)
            canvas = bg_img
        else:
            # обычный однотонный фон
            canvas = Image.new("RGB", (W, H), color=bg)

        x = (W - new_w) // 2
        y = (H - new_h) // 2
        canvas.paste(im_resized, (x, y))
        return canvas

    else:
        raise ValueError(f"Неизвестный режим mode={mode!r}")