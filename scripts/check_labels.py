"""Label sanity check: empty labels, out-of-range or tiny boxes, overlapping same-class boxes, class balance.

    python scripts/check_labels.py --dir data/splits
    python scripts/check_labels.py --dir data/labelled --images data/frames/images
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw, ih = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


def check(label_dir: Path, image_dir: Path | None, tiny_px: int, overlap: float) -> dict:
    files = sorted(label_dir.glob("*.txt"))
    res = {"images": len(files), "boxes": 0, "class_counts": Counter(), "empty": [], "bad_format": [],
           "out_of_range": [], "tiny": [], "overlapping": [], "missing_image": []}
    for lf in files:
        lines = [l.split() for l in lf.read_text().splitlines() if l.strip()]
        size = None
        if image_dir is not None:
            img = next((image_dir / f"{lf.stem}{e}" for e in (".jpg", ".png", ".jpeg") if (image_dir / f"{lf.stem}{e}").exists()), None)
            if img is None:
                res["missing_image"].append(lf.stem)
            else:
                im = cv2.imread(str(img))
                size = im.shape[:2] if im is not None else None
        if not lines:
            res["empty"].append(lf.stem)
            continue
        boxes = []
        for l in lines:
            if len(l) != 5 or not l[0].isdigit() or int(l[0]) >= len(CLASSES):
                res["bad_format"].append(lf.stem)
                continue
            c, b = int(l[0]), [float(v) for v in l[1:]]
            res["boxes"] += 1
            res["class_counts"][CLASSES[c]] += 1
            if any(v < 0 or v > 1 for v in b) or b[2] <= 0 or b[3] <= 0:
                res["out_of_range"].append(lf.stem)
            if size is not None and (b[2] * size[1] < tiny_px or b[3] * size[0] < tiny_px):
                res["tiny"].append(lf.stem)
            boxes.append((c, b))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if boxes[i][0] == boxes[j][0] and iou(boxes[i][1], boxes[j][1]) > overlap:
                    res["overlapping"].append(lf.stem)
    counts = res["class_counts"]
    res["class_counts"] = dict(counts)
    res["balance_ratio_min_over_max"] = round(min(counts.values()) / max(counts.values()), 3) if len(counts) == len(CLASSES) else 0.0
    for k in ("empty", "bad_format", "out_of_range", "tiny", "overlapping", "missing_image"):
        res[f"n_{k}"] = len(set(res[k]))
        res[k] = sorted(set(res[k]))[:30]
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/splits", help="a split root (train/val/test) or a folder with labels/")
    ap.add_argument("--images", default=None, help="image folder if not next to labels/")
    ap.add_argument("--tiny-px", type=int, default=8)
    ap.add_argument("--overlap", type=float, default=0.7)
    ap.add_argument("--out", default="evidence/M1/label_check.json")
    args = ap.parse_args()

    root = ROOT / args.dir
    report = {}
    subs = [s for s in ("train", "val", "test") if (root / s / "labels").exists()]
    if subs:
        for s in subs:
            report[s] = check(root / s / "labels", root / s / "images", args.tiny_px, args.overlap)
    else:
        report[root.name] = check(root / "labels", ROOT / args.images if args.images else root / "images",
                                  args.tiny_px, args.overlap)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    for k, r in report.items():
        print(f"{k:6s} images={r['images']} boxes={r['boxes']} classes={r['class_counts']} "
              f"empty={r['n_empty']} tiny={r['n_tiny']} overlap={r['n_overlapping']} bad={r['n_bad_format'] + r['n_out_of_range']}")


if __name__ == "__main__":
    main()
