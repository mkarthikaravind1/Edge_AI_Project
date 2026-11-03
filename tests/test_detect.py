import numpy as np

from edgevision.detect import decode_yolov8, letterbox
from edgevision.pipeline import draw, summarise_ms


def test_letterbox_keeps_aspect_and_pads() -> None:
    img = np.zeros((480, 640, 3), np.uint8)
    out, r, (px, py) = letterbox(img, 320)
    assert out.shape == (320, 320, 3)
    assert r == 0.5 and px == 0 and py == 40


def test_decode_maps_back_to_original_pixels_and_nms() -> None:
    # two overlapping boxes for class 1 and one weak box under the threshold
    pred = np.zeros((6, 3), np.float32)          # 4 + 2 classes, 3 anchors
    pred[:4, 0] = [160, 160, 100, 50]
    pred[:4, 1] = [162, 161, 100, 50]
    pred[:4, 2] = [50, 50, 20, 20]
    pred[5, 0], pred[5, 1], pred[4, 2] = 0.9, 0.8, 0.1
    dets = decode_yolov8(pred, ["body", "lid"], 0.25, 0.45, scale=0.5, pad=(0, 40), orig_shape=(480, 640))
    assert len(dets) == 1
    d = dets[0]
    assert d.name == "lid" and abs(d.conf - 0.9) < 1e-6
    assert np.allclose(d.box, (220, 190, 420, 290), atol=1)


def test_overlay_and_latency_summary() -> None:
    from edgevision.detect import Detection

    img = np.zeros((100, 100, 3), np.uint8)
    out = draw(img, [Detection(0, "body", 0.9, (10, 10, 50, 50))], fps=12.3)
    assert out.shape == img.shape and out.sum() > 0 and img.sum() == 0
    s = summarise_ms([0.01, 0.02, 0.03])
    assert s["median_ms"] == 20.0 and s["n"] == 3
