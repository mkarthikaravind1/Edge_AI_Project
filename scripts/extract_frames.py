"""Extract frames from my videos, drop blurry and near-duplicate ones, and record a manifest.

    python scripts/extract_frames.py --video data/raw/videos/clip1.mp4 --fps 3
    python scripts/extract_frames.py --video data/raw/videos/*.mp4 --fps 3      # several clips

Blur: variance of the Laplacian (low = blurry). Near-duplicate: perceptual-hash Hamming distance
to the last kept frame of the same video.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["file", "source", "video", "timestamp_s", "frame_idx", "blur_var", "phash", "seed", "group"]


def blur_var(img: np.ndarray) -> float:
    return float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def phash(img: np.ndarray) -> imagehash.ImageHash:
    return imagehash.phash(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))


def extract(video: Path, out_dir: Path, fps: float, blur_min: float, dup_max: int, max_side: int) -> tuple[list[dict], dict]:
    cap = cv2.VideoCapture(str(video))
    vfps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(vfps / fps))
    rows, stats = [], {"video": video.name, "video_fps": vfps, "frames_total": total, "sampled": 0,
                       "dropped_blur": 0, "dropped_dup": 0, "kept": 0}
    last_hash = None
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, img = cap.retrieve()
            if not ok:
                break
            stats["sampled"] += 1
            s = max_side / max(img.shape[:2])
            if s < 1:
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            bv = blur_var(img)
            if bv < blur_min:
                stats["dropped_blur"] += 1
            else:
                h = phash(img)
                if last_hash is not None and h - last_hash <= dup_max:
                    stats["dropped_dup"] += 1
                else:
                    last_hash = h
                    name = f"{video.stem}_{idx:06d}.jpg"
                    cv2.imwrite(str(out_dir / name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    rows.append({"file": name, "source": "real", "video": video.name,
                                 "timestamp_s": round(idx / vfps, 3), "frame_idx": idx,
                                 "blur_var": round(bv, 1), "phash": str(h), "seed": "", "group": ""})
                    stats["kept"] += 1
        idx += 1
    cap.release()
    return rows, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", nargs="+", required=True)
    ap.add_argument("--fps", type=float, default=3.0, help="frames sampled per second of video")
    ap.add_argument("--blur-min", type=float, default=60.0, help="Laplacian variance threshold")
    ap.add_argument("--dup-max", type=int, default=6, help="max pHash distance counted as duplicate")
    ap.add_argument("--max-side", type=int, default=1280)
    ap.add_argument("--out", default="data/frames")
    args = ap.parse_args()

    out = ROOT / args.out
    (out / "images").mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.csv"
    existing: list[dict] = []
    if manifest.exists():
        with open(manifest, newline="") as f:
            existing = list(csv.DictReader(f))

    videos = [Path(p) for pat in args.video for p in (glob.glob(pat) or [pat])]
    all_stats = []
    for v in videos:
        existing = [r for r in existing if r["video"] != v.name]   # re-running a video replaces it
        rows, st = extract(v, out / "images", args.fps, args.blur_min, args.dup_max, args.max_side)
        existing += rows
        all_stats.append(st)
        print(json.dumps(st))

    with open(manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(existing)

    ev = ROOT / "evidence/M1"
    ev.mkdir(parents=True, exist_ok=True)
    report = {"params": vars(args), "videos": all_stats, "kept_total": len(existing)}
    (ev / "extract_frames.json").write_text(json.dumps(report, indent=2))
    print(f"kept {len(existing)} frames total -> {manifest}" + ("  (target >= 150)" if len(existing) < 150 else ""))


if __name__ == "__main__":
    main()
