from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable, List, Optional

import click
from tqdm import tqdm

# ожидаем в vv/pipeline функцию build_video(...)
# сигнатура: build_video(images, out, sec_per, fps, size, bg, audio,
#                       transitions=False, audio_adjust="trim",
#                       progress_cb=None) -> Path
from .pipeline import build_video
from .config import IMAGE_EXTS, AUDIO_EXTS



def setup_logging(verbose: bool) -> None:
    lvl = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def collect_images(args: Iterable[str]) -> List[str]:
    paths: List[str] = []
    for item in args:
        p = Path(item)
        if p.is_dir():
            imgs = sorted(x for x in p.iterdir() if x.suffix.lower() in IMAGE_EXTS)
            if not imgs:
                raise click.ClickException(f"В папке нет изображений: {p}")
            paths += [str(x) for x in imgs]
        elif p.is_file():
            if p.suffix.lower() not in IMAGE_EXTS:
                raise click.ClickException(f"Неподдерживаемый формат изображения: {p.name}")
            paths.append(str(p))
        else:
            raise click.ClickException(f"Путь не найден: {p}")
    # удалим дубликаты, сохраним порядок
    seen = set()
    uniq = []
    for x in paths:
        if x not in seen:
            uniq.append(x); seen.add(x)
    if not uniq:
        raise click.ClickException("Не найдено ни одного изображения.")
    return uniq


def validate_audio(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise click.ClickException(f"Аудиофайл не найден: {p}")
    if p.suffix.lower() not in AUDIO_EXTS:
        raise click.ClickException("Аудио: поддерживаются только .mp3, .wav")
    return str(p)


def make_progress_cb():
    pbar = None

    def cb(current: int, total: int):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, desc="Рендер", unit="кадр")
        # обновляем точным значением (лучше, чем +1)
        pbar.n = current
        pbar.refresh()
        if current >= total:
            pbar.close()
    return cb


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--images", "-i", multiple=True, required=True,
              help="Один или несколько путей: файлы и/или папки с .jpg/.png")
@click.option("--audio", "-a", default=None,
              help="Путь к .mp3/.wav (опционально)")
@click.option("--out", "-o", default="output/video.mp4", show_default=True,
              help="Путь для сохранения результата")
@click.option("--sec-per", "--duration", type=click.FloatRange(min=0.05),
              default=4.0, show_default=True, help="Длительность кадра, сек")
@click.option("--fps", type=click.Choice(["24", "30", "60"], case_sensitive=False),
              default="30", show_default=True, help="Частота кадров")
@click.option("--width", type=int, default=1080, show_default=True)
@click.option("--height", type=int, default=1920, show_default=True)
@click.option("--bg", type=click.Choice(["black", "white"], case_sensitive=False),
              default="black", show_default=True, help="Цвет фона")
@click.option("--audio-adjust", type=click.Choice(["trim", "loop"], case_sensitive=False),
              default="trim", show_default=True, help="Подгонка аудио под длительность")
@click.option("--transitions/--no-transitions", default=False, show_default=True,
              help="Плавные переходы между кадрами")
@click.option("--info", is_flag=True, help="Вывести инфо о входных данных")
@click.option("--verbose", "-v", is_flag=True, help="Подробный лог")
def main(images, audio, out, sec_per, fps, width, height, bg, audio_adjust, transitions, info, verbose):
    """Vertical Video Maker — CLI."""
    setup_logging(verbose)

    imgs = collect_images(images)
    audio_path = validate_audio(audio)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if (width, height) != (1080, 1920):
        click.echo("⚠ Рекомендовано 1080x1920 для вертикальных роликов.")

    if info:
        click.echo(f"🖼  Изображений: {len(imgs)}")
        click.echo(f"   Примеры: {', '.join(Path(p).name for p in imgs[:3])}")
        if audio_path:
            click.echo(f"🎵 Аудио: {Path(audio_path).name}")
        click.echo(f"🎞  FPS: {fps} | ⏱ кадр: {sec_per}s | фон: {bg}")
        click.echo("")

    # грубая оценка числа кадров для прогресса (без учёта переходов)
    total_frames_est = int(len(imgs) * float(sec_per) * int(fps))
    progress_cb = make_progress_cb()

    click.echo("🎬 Рендер...")
    result = build_video(
        images=imgs,
        out=str(out_path),
        sec_per=float(sec_per),
        fps=int(fps),
        bg=bg.lower(),
        audio=audio_path,
        transitions=bool(transitions),
        audio_adjust=audio_adjust.lower(),
        progress_cb=progress_cb,
    )

    if not Path(result).exists():
        raise click.ClickException("Файл не создан.")

    size_mb = Path(result).stat().st_size / (1024 * 1024)
    click.echo(f"✅ Готово: {result}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()