from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Iterable

import click
from tqdm import tqdm

from .pipeline import build_video
from .config import IMAGE_EXTS, AUDIO_EXTS


def setup_logging(verbose: bool) -> None:
    lvl = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def collect_images(args: Iterable[str]) -> list[str]:
    paths: list[str] = []
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

    # remove duplicates, preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in paths:
        if x not in seen:
            uniq.append(x)
            seen.add(x)

    if not uniq:
        raise click.ClickException("Не найдено ни одного изображения.")
    return uniq


def validate_audio(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise click.ClickException(f"Аудиофайл не найден: {p}")
    if p.suffix.lower() not in AUDIO_EXTS:
        raise click.ClickException("Аудио: поддерживаются только .mp3, .wav")
    return str(p)


def make_progress_cb():
    pbar: tqdm | None = None

    def cb(current: int, total: int):
        # pipeline: 1..total = подготовка кадров (по изображениям)
        #            total+1   = encode
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, desc="Кадры", unit="img")

        if current <= total:
            pbar.n = current
            pbar.refresh()
        else:
            pbar.n = total
            pbar.set_description("Кодирование")
            pbar.refresh()
            pbar.close()

    return cb


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--images", "-i", multiple=True, required=True,
    help="Один или несколько путей: файлы и/или папки с изображениями"
)
@click.option("--audio", "-a", default=None, help="Путь к .mp3/.wav (опционально)")
@click.option("--out", "-o", default="output/video.mp4", show_default=True, help="Куда сохранить .mp4")
@click.option("--sec-per", "--duration", type=click.FloatRange(min=0.05),
              default=4.0, show_default=True, help="Длительность кадра, сек")
@click.option(
    "--total-duration", "--total",
    type=click.FloatRange(min=0.1),
    default=None,
    show_default=False,
    help="Общая длительность ролика в секундах. Если указано, имеет приоритет над --sec-per.",
)
@click.option("--fps", type=click.Choice(["24", "30", "60"], case_sensitive=False),
              default="30", show_default=True, help="FPS")
@click.option("--width", type=int, default=1080, show_default=True)
@click.option("--height", type=int, default=1920, show_default=True)
@click.option("--bg", type=click.Choice(["black", "white"], case_sensitive=False),
              default="black", show_default=True, help="Цвет фона (используется в cover / simple fit)")
@click.option("--audio-adjust", type=click.Choice(["trim", "loop"], case_sensitive=False),
              default="trim", show_default=True, help="Подгонка аудио под длительность")
@click.option("--transitions/--no-transitions", default=False, show_default=True,
              help="Плавные переходы между кадрами")
@click.option("--fit-mode", type=click.Choice(["fit", "cover"], case_sensitive=False),
              default="cover", show_default=True, help="fit — с полями, cover — с обрезкой")
@click.option("--fancy-bg/--no-fancy-bg", default=False, show_default=True,
              help="Размытый фон из самой картинки (имеет смысл только при fit-mode=fit)")
@click.option(
    "--motion",
    type=click.Choice(["none", "zoom", "kenburns"], case_sensitive=False),
    default="none",
    show_default=True,
    help="Движение: none / zoom / kenburns"
)
@click.option("--info", is_flag=True, help="Вывести инфо о входных данных и параметрах")
@click.option("--verbose", "-v", is_flag=True, help="Подробный лог")
def main(
    images,
    audio,
    out,
    sec_per,
    total_duration,
    fps,
    width,
    height,
    bg,
    fit_mode,
    fancy_bg,
    audio_adjust,
    transitions,
    motion,
    info,
    verbose,
):
    """Vertical Video Maker — CLI."""
    setup_logging(verbose)

    imgs = collect_images(images)
    audio_path = validate_audio(audio)

    out_path = Path(out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        if not click.confirm(f"Файл уже существует: {out_path.name}. Перезаписать?", default=False):
            raise click.Abort()

    if (width, height) != (1080, 1920):
        click.echo("⚠ Рекомендовано 1080x1920 для вертикальных роликов.")

    if fancy_bg and fit_mode.lower() != "fit":
        click.echo("⚠ fancy-bg имеет смысл только при fit-mode=fit (в cover игнорируется).")

    if info:
        click.echo(f"🖼  Изображений: {len(imgs)}")
        click.echo(f"   Примеры: {', '.join(Path(p).name for p in imgs[:3])}")
        if audio_path:
            click.echo(f"🎵 Аудио: {Path(audio_path).name}")
        click.echo(
            f"🎞  FPS: {int(fps)} | size: {width}x{height} | bg: {bg.lower()} | fit: {fit_mode.lower()} "
            f"| fancy_bg: {'on' if fancy_bg else 'off'} | motion: {motion.lower()} | transitions: {'on' if transitions else 'off'}"
        )
        if total_duration is not None:
            click.echo(f"⏱ total_duration: {total_duration:.2f}s (sec_per будет пересчитан)")
        else:
            click.echo(f"⏱ sec_per: {float(sec_per):.2f}s")
        click.echo("")

    progress_cb = make_progress_cb()

    click.echo("🎬 Рендер...")
    result = build_video(
        images=imgs,
        out=str(out_path),
        sec_per=float(sec_per),
        fps=int(fps),
        size=(int(width), int(height)),          # <-- фикс: реально используем
        bg=bg.lower(),
        audio=audio_path,
        transitions=bool(transitions),
        audio_adjust=audio_adjust.lower(),
        progress_cb=progress_cb,
        total_duration=total_duration,
        fit_mode=fit_mode.lower(),
        fancy_bg=bool(fancy_bg),
        motion=motion.lower(),
    )

    if not Path(result).exists():
        raise click.ClickException("Файл не создан.")

    size_mb = Path(result).stat().st_size / (1024 * 1024)
    click.echo(f"✅ Готово: {result}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()