from __future__ import annotations

from pathlib import Path
import wave
import shutil

import numpy as np
import pytest

from vv.audio import prepare_audio


def _write_wav(path: Path, duration_s: float, sr: int = 44100, hz: float = 440.0) -> None:
    n = int(sr * duration_s)
    t = np.arange(n, dtype=np.float32) / sr
    x = (0.2 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    pcm = (x * 32767).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def _can_run_audio_stack() -> bool:
    # если у тебя moviepy тянет imageio-ffmpeg, системный ffmpeg может и не требоваться,
    # но проверка всё равно полезна для “голых” окружений
    return shutil.which("ffmpeg") is not None or shutil.which("ffprobe") is not None


@pytest.mark.skipif(not _can_run_audio_stack(), reason="No ffmpeg/ffprobe in environment")
@pytest.mark.parametrize("target", [1.0, 2.5, 4.0])
def test_prepare_audio_trim(tmp_path: Path, target: float):
    wav = tmp_path / "long.wav"
    _write_wav(wav, duration_s=5.0)

    a = prepare_audio(str(wav), target_duration=target, mode="trim")
    assert a is not None
    assert hasattr(a, "duration")
    assert a.duration == pytest.approx(target, abs=0.10)


@pytest.mark.skipif(not _can_run_audio_stack(), reason="No ffmpeg/ffprobe in environment")
@pytest.mark.parametrize("target", [1.5, 2.5, 6.0])
def test_prepare_audio_loop(tmp_path: Path, target: float):
    wav = tmp_path / "short.wav"
    _write_wav(wav, duration_s=1.0)

    a = prepare_audio(str(wav), target_duration=target, mode="loop")
    assert a is not None
    assert hasattr(a, "duration")
    assert a.duration == pytest.approx(target, abs=0.10)