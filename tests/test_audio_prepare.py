from vv.audio import prepare_audio

def test_prepare_audio_trim():
    clip = prepare_audio("examples/audio/loop.mp3", target_duration=3.0, mode="trim")
    assert 2.5 <= clip.duration <= 3.0

def test_prepare_audio_loop():
    clip = prepare_audio("examples/audio/loop.mp3", target_duration=5.0, mode="loop")
    assert 4.5 <= clip.duration <= 5.5