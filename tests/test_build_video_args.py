from pathlib import Path

import pytest
from PIL import Image

from vv.pipeline import build_video


def _make_dummy_image(tmp_path: Path) -> Path:
    """Создаёт простую картинку для тестов и возвращает её путь."""
    img_path = tmp_path / "img.jpg"
    Image.new("RGB", (100, 100), color="red").save(img_path)
    return img_path


def test_no_images_raises(tmp_path: Path):
    out = tmp_path / "out.mp4"
    with pytest.raises(ValueError, match="Нет входных изображений"):
        build_video(
            images=[],               # пустой список
            out=out,
            sec_per=1.0,
            fps=30,
        )


def test_bad_fps_raises(tmp_path: Path):
    img = _make_dummy_image(tmp_path)
    out = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="fps должен быть > 0"):
        build_video(
            images=[img],
            out=out,
            sec_per=1.0,
            fps=0,                  # некорректный fps
        )


def test_bad_sec_per_without_total_duration(tmp_path: Path):
    img = _make_dummy_image(tmp_path)
    out = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="sec_per должна быть > 0"):
        build_video(
            images=[img],
            out=out,
            sec_per=0.0,           # некорректный sec_per
            fps=30,
        )


def test_bad_total_duration_raises(tmp_path: Path):
    img = _make_dummy_image(tmp_path)
    out = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="total_duration должна быть > 0"):
        build_video(
            images=[img],
            out=out,
            sec_per=1.0,
            fps=30,
            total_duration=0.0,    # некорректная общая длительность
        )


def test_bad_fit_mode_raises(tmp_path: Path):
    img = _make_dummy_image(tmp_path)
    out = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="Неизвестный режим fit_mode"):
        build_video(
            images=[img],
            out=out,
            sec_per=1.0,
            fps=30,
            fit_mode="weird",      # не "fit" и не "cover"
        )


def test_bad_audio_adjust_raises(tmp_path: Path):
    img = _make_dummy_image(tmp_path)
    out = tmp_path / "out.mp4"

    with pytest.raises(ValueError, match="Неизвестный режим audio_adjust"):
        build_video(
            images=[img],
            out=out,
            sec_per=1.0,
            fps=30,
            audio_adjust="stretch",  # не "trim" и не "loop"
        )