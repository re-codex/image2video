from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

import vv.pipeline as pl


class FakeEffect:
    def __init__(self, name: str, arg: float):
        self.name = name
        self.arg = arg


class FakeClip:
    def __init__(self, duration: float = 0.0):
        self.duration = float(duration)
        self.effects: list[object] = []
        self.fps: int | None = None
        self.audio = None

    def with_duration(self, d: float):
        self.duration = float(d)
        return self

    def with_effects(self, effects: list[object]):
        self.effects.extend(effects)
        return self

    def with_fps(self, fps: int):
        self.fps = int(fps)
        return self

    def with_audio(self, a):
        self.audio = a
        return self

    # методы, которые могут дергаться в других ветках
    def resized(self, *args, **kwargs):
        return self

    def with_position(self, *args, **kwargs):
        return self


class FakeVideo(FakeClip):
    def __init__(self, duration: float):
        super().__init__(duration=duration)
        self.write_calls: list[tuple[str, dict]] = []

    def write_videofile(self, filename: str, **kwargs):
        self.write_calls.append((filename, dict(kwargs)))
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_bytes(b"")  # маркер “файл создан”


def _mk_img(path: Path, w: int = 640, h: int = 480) -> None:
    Image.new("RGB", (w, h), (20, 30, 40)).save(path)


def test_pipeline_smoke_no_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    img1 = tmp_path / "1.png"
    img2 = tmp_path / "2.png"
    _mk_img(img1)
    _mk_img(img2)

    out = tmp_path / "out.mp4"

    progress: list[tuple[int, int]] = []

    def progress_cb(cur: int, total: int) -> None:
        progress.append((cur, total))

    # fit_to_canvas не должен делать тяжелую работу в смоук-тесте
    def fake_fit_to_canvas(_p, *, size, **_kwargs):
        w, h = size
        return Image.new("RGB", (w, h), (1, 2, 3))

    monkeypatch.setattr(pl, "fit_to_canvas", fake_fit_to_canvas, raising=True)

    # moviepy-клипы подменяем на фейки (устойчиво к изменениям API moviepy 2.x)
    monkeypatch.setattr(pl, "ImageClip", lambda _arr: FakeClip(), raising=True)

    captured_concat: dict = {}

    def fake_concat(clips: list[FakeClip], method: str = "compose", padding: float = 0.0):
        captured_concat["method"] = method
        captured_concat["padding"] = padding
        total = sum(c.duration for c in clips)
        if padding:
            total = total + float(padding) * (len(clips) - 1)
        return FakeVideo(total)

    monkeypatch.setattr(pl, "concatenate_videoclips", fake_concat, raising=True)

    # audio не трогаем в этом тесте
    monkeypatch.setattr(pl, "prepare_audio", lambda *a, **k: None, raising=True)

    result = pl.build_video(
        images=[img1, img2],
        out=out,
        sec_per=0.2,
        fps=24,
        size=(360, 640),
        transitions=False,
        motion="none",
        progress_cb=progress_cb,
        fit_mode="fit",
        fancy_bg=True,
    )

    assert result == str(out)
    assert out.exists()

    # прогресс: старт 0/n, потом 1..n, потом encode-сигнал (n+1, n)
    assert progress[0] == (0, 2)
    assert (1, 2) in progress
    assert (2, 2) in progress
    assert progress[-1] == (3, 2)

    # concatenate_videoclips в "compose"
    assert captured_concat["method"] == "compose"


def test_pipeline_transitions_apply_crossfade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    img1 = tmp_path / "1.png"
    img2 = tmp_path / "2.png"
    _mk_img(img1)
    _mk_img(img2)

    out = tmp_path / "out.mp4"

    # облегченная картинка-кадр
    monkeypatch.setattr(
        pl,
        "fit_to_canvas",
        lambda _p, *, size, **_k: Image.new("RGB", size, (9, 9, 9)),
        raising=True,
    )

    monkeypatch.setattr(pl, "ImageClip", lambda _arr: FakeClip(), raising=True)

    # фиксируем fade и эффект
    monkeypatch.setattr(pl, "fade_for", lambda _sec_per: 0.4, raising=True)
    monkeypatch.setattr(pl, "CrossFadeIn", lambda fade: FakeEffect("crossfadein", fade), raising=True)

    seen: dict = {}

    def fake_concat(clips: list[FakeClip], method: str = "compose", padding: float = 0.0):
        seen["clips"] = clips
        seen["method"] = method
        seen["padding"] = padding
        total = sum(c.duration for c in clips) + float(padding) * (len(clips) - 1)
        return FakeVideo(total)

    monkeypatch.setattr(pl, "concatenate_videoclips", fake_concat, raising=True)
    monkeypatch.setattr(pl, "prepare_audio", lambda *a, **k: None, raising=True)

    pl.build_video(
        images=[img1, img2],
        out=out,
        sec_per=1.0,
        fps=24,
        size=(360, 640),
        transitions=True,
        motion="none",
        fit_mode="fit",
        fancy_bg=True,
    )

    clips = seen["clips"]
    assert len(clips) == 2
    assert clips[0].effects == []  # первый без эффекта
    assert len(clips[1].effects) == 1
    eff = clips[1].effects[0]
    assert getattr(eff, "name", None) == "crossfadein"
    assert getattr(eff, "arg", None) == 0.4
    assert seen["padding"] == -0.4