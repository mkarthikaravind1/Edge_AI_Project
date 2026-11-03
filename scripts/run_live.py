"""M1.2: live overlay - boxes, class labels, per-class count, FPS.

    python scripts/run_live.py                         # config camera + detector
    python scripts/run_live.py --source video --path data/raw/videos/clip1.mp4
    python scripts/run_live.py --headless --seconds 30 --save evidence/M1/live_overlay.mp4

Press q to quit, s to save a screenshot to evidence/M1/.
"""

from __future__ import annotations

import argparse
import time

import cv2

from edgevision.config import ROOT, load_config
from edgevision.detect import make_detector
from edgevision.hal import make_camera
from edgevision.pipeline import FpsMeter, draw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["webcam", "video", "picamera2"], default=None)
    ap.add_argument("--path", default=None)
    ap.add_argument("--backend", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--headless", action="store_true", help="no window (Pi over SSH)")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--save", default=None, help="write the overlay video here")
    args = ap.parse_args()

    cfg = load_config()
    if args.source:
        cfg["camera"]["type"] = args.source
    if args.path:
        cfg["camera"]["path"] = args.path
    if args.backend:
        cfg["detector"]["backend"] = args.backend
    if args.model:
        cfg["detector"]["model"] = args.model

    det = make_detector(cfg["detector"], cfg["classes"])
    cam = make_camera(cfg["camera"], realtime=True)
    meter = FpsMeter()
    writer = None
    t0 = time.perf_counter()
    shots = 0
    try:
        while args.seconds is None or time.perf_counter() - t0 < args.seconds:
            fr = cam.read()
            if fr is None:
                break
            dets = det.detect(fr.image)
            out = draw(fr.image, dets, meter.tick(), [cfg["detector"]["backend"]])
            if args.save:
                if writer is None:
                    p = ROOT / args.save
                    p.parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 15, out.shape[1::-1])
                writer.write(out)
            if not args.headless:
                cv2.imshow("edgevision", out)
                k = cv2.waitKey(1) & 0xFF
                if k == ord("q"):
                    break
                if k == ord("s"):
                    shots += 1
                    p = ROOT / "evidence/M1" / f"live_overlay_{shots}.png"
                    cv2.imwrite(str(p), out)
                    print(f"saved {p}")
    finally:
        cam.close()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
    print(f"final FPS {meter.fps:.1f}")


if __name__ == "__main__":
    main()
