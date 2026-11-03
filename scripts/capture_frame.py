"""M1.1: grab one frame from the configured camera -> evidence/M1/first_frame.png (+ json with host info).

    EDGE_TARGET=laptop python scripts/capture_frame.py
    EDGE_TARGET=pi     python scripts/capture_frame.py --name first_frame_pi
"""

from __future__ import annotations

import argparse
import time

import cv2

from edgevision.config import load_config
from edgevision.evidence import evidence_dir, write_json
from edgevision.hal import make_camera


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="first_frame")
    ap.add_argument("--warmup", type=int, default=10, help="frames to discard while auto-exposure settles")
    args = ap.parse_args()

    cfg = load_config()
    with make_camera(cfg["camera"], realtime=False) as cam:
        for _ in range(args.warmup):
            cam.read()
            time.sleep(0.03)
        fr = cam.read()
    if fr is None:
        raise SystemExit("camera returned no frame")
    path = evidence_dir("M1") / f"{args.name}.png"
    cv2.imwrite(str(path), fr.image)
    h, w = fr.image.shape[:2]
    write_json("M1", args.name, {"camera": cfg["camera"]["type"], "width": w, "height": h, "file": path.name})
    print(f"saved {path} ({w}x{h})")


if __name__ == "__main__":
    main()
