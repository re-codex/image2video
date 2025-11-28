from __future__ import annotations

from pathlib import Path
import pytest
from PIL import Image

import vv.pipeline as pl


def _mk_img(path: Path) -> None:
    Image.new("RGB", (640, 480), (10, 20, 30)).save(path)


def test_pipeline_total_duration_uses_sec_per_for_total(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    img1 = tmp_path / "1.png"
    img2 = tmp_path / "2.png"
    _mk_img(img1)
    _mk_img(img2)

    out = tmp_path / "out.mp4"

    monkeypatch.setattr(
        pl,
        "fit_to_canvas",
        lambda _p, *, size, **_k: Image.new("RGB", size, (1, 1, 1)),
        raising=True,
    )
    monkeypatch.setattr(pl, "ImageClip", lambda _arr: type("C", (), {"with_duration": lambda self, d: self, "duration": 1.0})(), raising=True)

    called = {"ok": False}

    def fake_sec_per_for_total(n: int, total: float, transitions: bool):
        called["ok"] = True
        assert n == 2
        assert total == 10.0
        assert transitions is True
        return 3.3

    monkeypatch.setattr(pl, "sec_per_for_total", fake_sec_per_for_total, raising=True)
    monkeypatch.setattr(pl, "fade_for", lambda _sec: 0.4, raising=True)
    monkeypatch.setattr(pl, "CrossFadeIn", lambda _fade: object(), raising=True)

    class Clip:
        def __init__(self):
            self.duration = 0.0
        def with_duration(self, d):
            self.duration = float(d)
            return self
        def with_effects(self, _eff):
            return self

    monkeypatch.setattr(pl, "ImageClip", lambda _arr: Clip(), raising=True)

    def fake_concat(clips, method="compose", padding=0.0):
        v = type("V", (), {})()
        v.duration = sum(c.duration for c in clips) + float(padding) * (len(clips) - 1)
        v.with_fps = lambda _fps: v
        v.with_audio = lambda _a: v
        v.write_videofile = lambda filename, **kwargs: Path(filename).write_bytes(b"")
        return v

    monkeypatch.setattr(pl, "concatenate_videoclips", fake_concat, raising=True)
    monkeypatch.setattr(pl, "prepare_audio", lambda *a, **k: None, raising=True)

    pl.build_video(
        images=[img1, img2],
        out=out,
        sec_per=999.0,  # должен быть переопределён
        fps=24,
        size=(360, 640),
        total_duration=10.0,
        transitions=True,
        motion="none",
        fit_mode="fit",
        fancy_bg=True,
    )

    assert called["ok"] is True
    assert out.exists()