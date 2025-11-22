from pathlib import Path
from vv.pipeline import build_video

def test_build_video_smoke(tmp_path):
    # берём готовые examples/images и audio
    base = Path(__file__).resolve().parents[1]
    img_dir = base / "examples" / "images"
    audio = base / "examples" / "audio" / "loop.mp3"

    out = tmp_path / "test.mp4"

    result = build_video(
        images=str(img_dir),
        out=str(out),
        sec_per=1.0,
        fps=10,
        bg="black",
        audio=str(audio),
    )

    assert Path(result).exists()
    assert Path(result).stat().st_size > 0