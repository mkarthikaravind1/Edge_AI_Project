"""Box-aware augmentation of the TRAIN split only (run after split.py, never before).

    python scripts/augment.py --copies 2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import albumentations as A
import cv2

ROOT = Path(__file__).resolve().parents[1]


def clip_yolo(b: list[float]) -> list[float]:
    """Clip a (cx, cy, w, h) box so its corners lie inside [0, 1] (float rounding can push edges to -1e-7)."""
    x1, y1 = max(0.0, b[0] - b[2] / 2), max(0.0, b[1] - b[3] / 2)
    x2, y2 = min(1.0, b[0] + b[2] / 2), min(1.0, b[1] + b[3] / 2)
    return [(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1]


def pipeline() -> A.Compose:
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.Affine(scale=(0.8, 1.2), translate_percent=(-0.1, 0.1), rotate=(-5, 5), p=0.7),
            A.RandomBrightnessContrast(0.25, 0.25, p=0.7),
            A.HueSaturationValue(8, 20, 15, p=0.4),
            A.OneOf([A.MotionBlur(blur_limit=5), A.GaussianBlur(blur_limit=(3, 5))], p=0.3),
            A.GaussNoise(std_range=(0.01, 0.05), p=0.3),
            A.ImageCompression(quality_range=(60, 95), p=0.3),
        ],
        bbox_params=A.BboxParams(format="yolo", label_fields=["cls"], min_visibility=0.4),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", default="data/splits/train")
    ap.add_argument("--copies", type=int, default=2)
    ap.add_argument("--real-only", action="store_true", help="augment real frames only (skip syn_*)")
    args = ap.parse_args()

    d = ROOT / args.split_dir
    if d.name != "train":
        raise SystemExit("augmentation is only allowed on the train split")
    tf = pipeline()
    src = [p for p in sorted((d / "images").glob("*.jpg")) if not p.stem.startswith("aug_")]
    if args.real_only:
        src = [p for p in src if not p.stem.startswith("syn_")]
    made = 0
    for p in src:
        img = cv2.imread(str(p))
        lines = [l.split() for l in (d / "labels" / f"{p.stem}.txt").read_text().splitlines() if l.strip()]
        boxes = [clip_yolo([float(v) for v in l[1:]]) for l in lines]
        cls = [int(l[0]) for l in lines]
        for k in range(args.copies):
            r = tf(image=img, bboxes=boxes, cls=cls)
            stem = f"aug_{p.stem}_{k}"
            cv2.imwrite(str(d / "images" / f"{stem}.jpg"), r["image"])
            (d / "labels" / f"{stem}.txt").write_text(
                "".join(f"{int(c)} " + " ".join(f"{v:.6f}" for v in clip_yolo(list(b))) + "\n"
                        for c, b in zip(r["cls"], r["bboxes"])))
            made += 1
    ev = ROOT / "evidence/M1"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "augment.json").write_text(json.dumps({"split": "train", "source_images": len(src),
                                                 "augmented_created": made, "copies": args.copies,
                                                 "transforms": [t.__class__.__name__ for t in tf.transforms]}, indent=2))
    print(f"created {made} augmented train images from {len(src)}")


if __name__ == "__main__":
    main()
