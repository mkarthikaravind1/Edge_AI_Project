"""M5.1/M5.2: photograph parts on the fixed rig, sorted into the folders the calibration + pass/fail test use.

Live view with a centring guide and the detector's boxes. Keys:
  c  save as CALIBRATION good part    -> data/rig/calib_good/
  g  save as TEST good part           -> data/rig/test/good/
  d  save as TEST defective part      -> data/rig/test/defective/   (asks nothing: name the defect in the filename later)
  1-4 set the defect type for the next 'd' (1 mark, 2 chipped corner, 3 lid missing, 4 lid not seated)
  q  quit
Use DIFFERENT physical parts / placements for calibration and test (calibration ~15 good shots, test 10 + 10).

    EDGE_TARGET=pi python scripts/capture_rig.py          (needs a screen on the Pi, or VNC)
    EDGE_TARGET=pi python scripts/capture_rig.py --headless --label g     # one shot per run over SSH
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from edgevision.config import load_config
from edgevision.detect import make_detector
from edgevision.hal import make_camera
from edgevision.pipeline import draw

ROOT = Path(__file__).resolve().parents[1]
DEFECTS = {ord("1"): "mark", ord("2"): "chip", ord("3"): "lidmissing", ord("4"): "lidnotseated"}
DIRS = {"c": "calib_good", "g": "test/good", "d": "test/defective"}


def save(img, label: str, defect: str) -> Path:
    d = ROOT / "data/rig" / DIRS[label]
    d.mkdir(parents=True, exist_ok=True)
    prefix = f"{defect}_" if label == "d" else ""
    p = d / f"{prefix}{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    counts = {k: len(list((ROOT / 'data/rig' / v).glob('*.jpg'))) for k, v in DIRS.items()}
    print(f"saved {p.relative_to(ROOT)}   counts: calib {counts['c']}  good {counts['g']}  defective {counts['d']}")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--label", choices=["c", "g", "d"], help="headless: label of the single shot")
    ap.add_argument("--defect", default="mark", choices=list(DEFECTS.values()))
    args = ap.parse_args()
    cfg = load_config()
    cam = make_camera(cfg["camera"], realtime=True)
    det = make_detector(cfg["detector"], cfg["classes"])
    if args.headless:
        for _ in range(10):                 # let exposure settle
            cam.read()
        fr = cam.read()
        save(fr.image, args.label or "g", args.defect)
        cam.close()
        return
    defect = "mark"
    while True:
        fr = cam.read()
        if fr is None:
            continue
        vis = draw(fr.image, det.detect(fr.image), None, [f"next defect: {defect}", "c/g/d save  1-4 defect  q quit"])
        h, w = vis.shape[:2]
        cv2.rectangle(vis, (int(w * 0.2), int(h * 0.2)), (int(w * 0.8), int(h * 0.8)), (0, 255, 255), 1)   # keep part inside
        cv2.imshow("rig capture", vis)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k in DEFECTS:
            defect = DEFECTS[k]
        elif chr(k) in DIRS:
            save(fr.image, chr(k), defect)
    cam.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
