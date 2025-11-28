from __future__ import annotations
from pathlib import Path
from collections.abc import Iterable, Callable
import random
import math
import numpy as np
from moviepy import ImageClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video.fx import CrossFadeIn

from .image import fit_to_canvas
from .audio import prepare_audio
from .config import WIDTH, HEIGHT, BG, IMAGE_EXTS
from .duration import fade_for, sec_per_for_total

from PIL import Image, ImageOps, ImageFilter

PathLike = str | Path
CropOffsets = dict[str, tuple[float, float]]
ProgressCB = Callable[[int, int], None] | None

def _collect_images(images: PathLike | Iterable[PathLike]) -> list[Path]:
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
    images: PathLike | Iterable[PathLike],
    out: PathLike,
    sec_per: float,
    fps: int,
    size: tuple[int, int] = (WIDTH, HEIGHT),
    bg: str = BG,
    audio: PathLike | None = None,
    transitions: bool = False,
    motion: str = "none",           # "none" | "zoom" | "kenburns"
    audio_adjust: str = "trim",
    progress_cb: ProgressCB = None,
    total_duration: float | None = None,
    fit_mode: str = "fit",
    fancy_bg: bool = True,
    crop_offsets: CropOffsets | None = None,
) -> str:
    """Основной пайплайн: картинки -> вертикальное видео (+ опционально аудио)."""

    # --- сбор картинок ---
    img_paths = _collect_images(images)
    if not img_paths:
        raise ValueError("Нет входных изображений")

    n = len(img_paths)

    # --- нормализация режимов ---
    fit_mode = fit_mode.lower()
    audio_adjust = audio_adjust.lower()
    motion = motion.lower()

    # --- валидация аргументов ---
    if fps <= 0:
        raise ValueError("fps должен быть > 0")

    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("size должен быть положительными числами (width, height)")

    if total_duration is not None:
        if total_duration <= 0:
            raise ValueError("total_duration должна быть > 0")
    else:
        if sec_per <= 0:
            raise ValueError("sec_per должна быть > 0, если total_duration не задана")

    if fit_mode not in {"fit", "cover"}:
        raise ValueError(f"Неизвестный режим fit_mode={fit_mode!r}")

    if audio_adjust not in {"trim", "loop"}:
        raise ValueError(f"Неизвестный режим audio_adjust={audio_adjust!r}")

    allowed_motion = {"none", "zoom", "kenburns"}
    if motion not in allowed_motion:
        raise ValueError(
            f"motion должен быть 'none', 'zoom' или 'kenburns', а не {motion!r}"
        )

    # --- вычисление sec_per с учётом total_duration ---
    if total_duration is not None:
        if transitions and n > 1:
            sec_per = sec_per_for_total(n, float(total_duration), transitions=True)
        else:
            sec_per = float(total_duration) / n
    else:
        # sec_per уже валиден
        pass

    sec_per = float(sec_per)
    W, H = size

    # старт прогресса
    if progress_cb:
        progress_cb(0, len(img_paths))

    clips: list[ImageClip] = []

    # --- Логика "Пачек" (Batching) для Ken Burns ---
    # Чтобы движения шли сериями: 3 зума, потом 2 панорамы и т.д.

    # Состояния пачки
    batch_remaining = 0
    current_move_type = "zoom"

    # 0 = Первичное направление (Left / Top / ZoomIn)
    # 1 = Вторичное направление (Right / Bottom / ZoomOut)
    batch_direction_flag = 0

    for idx, p in enumerate(img_paths, 1):

        # 1. Определяем тип движения для текущего кадра
        if batch_remaining <= 0:
            # Начинаем новую серию
            batch_remaining = random.randint(2, 4) # 2-4 кадра в одном стиле

            # Выбираем тип движения
            r = random.random()
            if r < 0.30:
                current_move_type = "zoom" # Zoom In/Out
            else:
                current_move_type = "pan"  # Pan Left/Right/Up/Down

            # Генерируем единое направление для всей пачки
            batch_direction_flag = random.randint(0, 1)

        batch_remaining -= 1

        # --- Подготовка изображения ---
        with Image.open(p) as im:
            im_pil = ImageOps.exif_transpose(im).convert("RGB")

        if motion == "kenburns":
            # == Вспомогательная функция плавности (ease-in-out) ==
            def alpha(t: float) -> float:
                if sec_per <= 0: return 0.0
                x = min(max(t / sec_per, 0.0), 1.0)
                # Ease-in-out sine
                return 0.5 - 0.5 * math.cos(math.pi * x)

            # ---------------------------------------------------------
            # ВЕТКА 1: COVER (Весь экран заполнен, двигаем саму картинку)
            # ---------------------------------------------------------
            if fit_mode == "cover":
                scale_base = max(W / im_pil.width, H / im_pil.height)

                # Запас на движение (Overscan)
                overscan = 0.06 # 6%
                k = scale_base * (1.0 + overscan)

                new_w, new_h = int(im_pil.width * k), int(im_pil.height * k)
                im_resized = im_pil.resize((new_w, new_h), Image.LANCZOS)
                base_clip = ImageClip(np.array(im_resized)).with_duration(sec_per)

                max_dx = max(0, new_w - W)
                max_dy = max(0, new_h - H)
                cx, cy = max_dx / 2.0, max_dy / 2.0

                # Инициализация переменных
                start_x, end_x = cx, cx
                start_y, end_y = cy, cy
                s_start, s_end = 1.0, 1.0

                if current_move_type == "zoom":
                    # Используем флаг направления пачки для Zoom In vs Zoom Out
                    if batch_direction_flag == 0: # Zoom In
                        s_start, s_end = 1.0, 1.05
                    else: # Zoom Out
                        s_start, s_end = 1.05, 1.0

                else: # Pan
                    s_start = s_end = 1.005 # Легкий фикс краев
                    is_horz = max_dx > max_dy
                    travel = 0.7 # 70% доступного пути

                    if is_horz:
                        dist = max_dx * travel
                        if batch_direction_flag == 0: # Left -> Right
                            start_x, end_x = cx - dist/2, cx + dist/2
                        else: # Right -> Left
                            start_x, end_x = cx + dist/2, cx - dist/2
                    else:
                        dist = max_dy * travel
                        if batch_direction_flag == 0: # Top -> Bottom
                            start_y, end_y = cy - dist/2, cy + dist/2
                        else: # Bottom -> Top
                            start_y, end_y = cy + dist/2, cy - dist/2

                # Биндим значения (closure fix)
                def pos_f(t, x0=start_x, x1=end_x, y0=start_y, y1=end_y):
                    a = alpha(t)
                    # Двигаем контент влево (-x), чтобы камера шла вправо
                    return -(x0 + (x1 - x0)*a), -(y0 + (y1 - y0)*a)

                def scale_f(t, s0=s_start, s1=s_end):
                    return s0 + (s1 - s0)*alpha(t)

                final_clip = (
                    base_clip
                    .resized(new_size=scale_f)
                    .with_position(pos_f)
                )

                clip = CompositeVideoClip([final_clip], size=(W, H)).with_duration(sec_per)

            # ---------------------------------------------------------
            # ВЕТКА 2: FIT (iOS Style - Stable Frame, Moving Content)
            # ---------------------------------------------------------
            else:
                # 1. Создаем Фон (Blur)
                bg_im = ImageOps.fit(im_pil, (W, H), Image.LANCZOS)
                bg_im = bg_im.filter(ImageFilter.GaussianBlur(radius=35))
                bg_clip = ImageClip(np.array(bg_im)).with_duration(sec_per)

                # 2. Вычисляем размер "Окна" (Рамки)
                ratio_im = im_pil.width / im_pil.height
                ratio_screen = W / H

                if ratio_im > ratio_screen:
                    # Широкая - упирается в края по ширине
                    fit_w = W
                    fit_h = int(W / ratio_im)
                else:
                    # Высокая - упирается в края по высоте
                    fit_h = H
                    fit_w = int(H * ratio_im)

                # 3. Готовим контент ДЛЯ окна (с запасом на движение)
                # Мы делаем контент больше самого окна (fit_w/h) на X%
                overscan = 0.08 # 8% запаса внутри рамки

                content_w = int(fit_w * (1.0 + overscan))
                content_h = int(fit_h * (1.0 + overscan))

                img_content = im_pil.resize((content_w, content_h), Image.LANCZOS)
                content_clip = ImageClip(np.array(img_content)).with_duration(sec_per)

                # Доступное пространство внутри окна
                max_dx = content_w - fit_w
                max_dy = content_h - fit_h

                # Центр контента относительно левого верхнего угла окна
                # В идеале центр контента должен быть в (fit_w/2, fit_h/2)
                # Но так как контент больше, его координата "центра" для MoviePy - это сдвиг
                # Начальная позиция (чтобы было по центру):
                base_x = -(max_dx / 2.0)
                base_y = -(max_dy / 2.0)

                start_x, end_x = base_x, base_x
                start_y, end_y = base_y, base_y
                s_start, s_end = 1.0, 1.0

                # Логика движения (ВНУТРИ рамки)
                if current_move_type == "zoom":
                    if batch_direction_flag == 0:
                        s_start, s_end = 1.0, 1.05 # Zoom In
                    else:
                        s_start, s_end = 1.05, 1.0 # Zoom Out
                else:
                    # Pan
                    is_wide_relative = (im_pil.width / im_pil.height) > (W / H)
                    travel = 0.8

                    if is_wide_relative:
                        # Картинка широкая, fit_w == W. Двигаем горизонтально
                        dist = max_dx * travel
                        if batch_direction_flag == 0:
                            start_x, end_x = base_x - dist/2, base_x + dist/2
                        else:
                            start_x, end_x = base_x + dist/2, base_x - dist/2
                    else:
                        dist = max_dy * travel
                        if batch_direction_flag == 0:
                            start_y, end_y = base_y - dist/2, base_y + dist/2
                        else:
                            start_y, end_y = base_y + dist/2, base_y - dist/2

                def pos_f_fit(t, x0=start_x, x1=end_x, y0=start_y, y1=end_y):
                    a = alpha(t)
                    return x0 + (x1 - x0)*a, y0 + (y1 - y0)*a

                def scale_f_fit(t, s0=s_start, s1=s_end):
                    return s0 + (s1 - s0)*alpha(t)

                # 4. АНИМАЦИЯ КОНТЕНТА
                moving_content = (
                    content_clip
                    .resized(new_size=scale_f_fit)
                    .with_position(pos_f_fit)
                )

                # 5. МАСКИРОВКА (CLIPPING)
                # Создаем композицию размером ровно с рамку (fit_w, fit_h).
                # Всё, что выходит за пределы этого размера, обрежется.
                masked_content = CompositeVideoClip(
                    [moving_content],
                    size=(fit_w, fit_h)
                ).with_duration(sec_per)

                # 6. ФИНАЛЬНАЯ СБОРКА
                # Кладем маскированный контент по центру экрана поверх блюра
                clip = CompositeVideoClip(
                    [bg_clip, masked_content.with_position("center")],
                    size=(W, H)
                ).with_duration(sec_per)

        # -------------------------------------------------------------
        # ВЕТКА 3: СТАТИКА / ПРОСТОЙ ZOOM (НЕ KEN BURNS)
        # -------------------------------------------------------------
        else:
            offset = crop_offsets.get(str(p)) if crop_offsets else None

            # Используем обычную функцию для статики (она эффективнее)
            # Но для motion="zoom" логику группировки тоже нужно оставить
            frame = fit_to_canvas(p, size=(W, H), bg=bg, mode=fit_mode, fancy_bg=fancy_bg, offset=offset)
            frame_arr = np.array(frame)
            clip = ImageClip(frame_arr).with_duration(sec_per)

            if motion == "zoom":
                # Простой Zoom без панорамирования
                # Также используем batch_direction_flag
                strength = 0.03
                if batch_direction_flag == 0:
                    z0, z1 = 1.0, 1.0 + strength
                else:
                    z0, z1 = 1.0 + strength, 1.0

                def zoom_simple(t, s=z0, e=z1):
                    a = 0.5 - 0.5 * math.cos(math.pi * (t/sec_per))
                    return s + (e - s) * a

                clip = clip.resized(new_size=zoom_simple)

        clips.append(clip)
        if progress_cb: progress_cb(idx, n)

    if not clips:
        raise ValueError("Не удалось создать ни одного клипа")

    # ---- Переходы ----
    if transitions and len(clips) > 1:
        fade = fade_for(sec_per)
        clips_with_fx = [clips[0]] + [c.with_effects([CrossFadeIn(fade)]) for c in clips[1:]]
        video = concatenate_videoclips(clips_with_fx, method="compose", padding=-fade)
    else:
        video = concatenate_videoclips(clips, method="compose")

    video = video.with_fps(int(fps))

    # аудио
    if audio:
        a = prepare_audio(str(audio), target_duration=video.duration, mode=audio_adjust)
        if a: video = video.with_audio(a)

    # Сообщаем GUI, что обработка кадров закончилась,
    # и началось кодирование итогового ролика.
    if progress_cb:
        # current > total — специальный сигнал "encode"
        progress_cb(len(img_paths) + 1, len(img_paths))

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    video.write_videofile(
        str(out_path),
        codec="libx264",
        audio_codec="aac",
        fps=int(fps),
    )

    return str(out_path)