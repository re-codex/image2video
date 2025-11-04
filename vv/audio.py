from __future__ import annotations
from pathlib import Path
from typing import Optional
from moviepy import AudioFileClip, concatenate_audioclips

def prepare_audio(path: Optional[str], target_duration: float, mode: str = "trim"):
    """
    Вернёт AudioFileClip ровно нужной длительности.
    mode: "trim" — обрезать; "loop" — зациклить до длины.
    """
    if not path:
        return None

    clip = AudioFileClip(str(Path(path)))

    if mode.lower() == "loop":
        # Пытаемся использовать эффект v2
        try:
            from moviepy.audio.fx import AudioLoop
            clip = clip.with_effects([AudioLoop(duration=float(target_duration))])
        except Exception:
            # Фолбэк: ручная склейка до нужной длины
            parts = []
            acc = 0.0
            while acc + 1e-6 < target_duration:  # защита от накопл. ошибки
                rem = target_duration - acc
                part = clip if clip.duration <= rem else clip.subclipped(0, rem)
                parts.append(part)
                acc += part.duration
            clip = concatenate_audioclips(parts)
    else:
        # "trim" по умолчанию
        clip = clip.subclipped(0, min(clip.duration, target_duration))

    # опционально мягкие края:
    # from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
    # clip = clip.with_effects([AudioFadeIn(0.2), AudioFadeOut(0.2)])

    return clip