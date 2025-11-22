from vv.image import fit_to_canvas

def test_fit_to_canvas_aspect():
    out = fit_to_canvas("examples/images/test_frame_1.png", size=(1080, 1920), bg="black")
    assert out.size == (1080, 1920)