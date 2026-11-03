"""Pre-label real frames so I only REVIEW and CORRECT boxes, never draw from scratch.

Two passes:
  1. --world                          zero-shot YOLO-World with text prompts (no training). Good boxes, weak classes.
  2. --model models/prelabel.pt       a helper YOLO trained on my first reviewed frames + CAD renders
                                      (scripts/train_prelabel.py). Much better classes.
Frames I already reviewed (data/labelled/reviewed.csv) are never overwritten.

Writes YOLO .txt files to data/labelled/labels/ (+ classes.txt) and a CVAT "YOLO 1.1" zip as an
alternative to the offline review tool (scripts/review_labels.py).

    python scripts/autolabel.py --world
    python scripts/autolabel.py --model models/prelabel.pt
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
PROMPTS = {  # YOLO-World prompt -> my class
    "closed white plastic box": 0,
    "white plastic tray with two round holes": 1,
    "thin flat white plastic plate": 2,
    "white plastic lid": 2,
}


def reviewed_set(label_root: Path) -> set[str]:
    f = label_root / "reviewed.csv"
    if not f.exists():
        return set()
    with open(f, newline="") as fh:
        return {r["file"] for r in csv.DictReader(fh)}


def iou_xywh(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    inter = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="data/frames/images")
    ap.add_argument("--out", default="data/labelled")
    ap.add_argument("--model", default=None, help="YOLO .pt trained on my classes")
    ap.add_argument("--world", action="store_true", help="use zero-shot YOLO-World instead")
    ap.add_argument("--world-weights", default="yolov8s-worldv2.pt")
    ap.add_argument("--conf", type=float, default=None, help="default 0.12 for --world, 0.25 for --model")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--max-iou", type=float, default=0.6, help="class-agnostic de-duplication of boxes")
    ap.add_argument("--overwrite-reviewed", action="store_true", help="DANGER: replace labels I already reviewed")
    args = ap.parse_args()
    if not args.model and not args.world:
        raise SystemExit("pass --model <weights.pt> or --world")
    conf = args.conf if args.conf is not None else (0.12 if args.world else 0.25)

    from ultralytics import YOLO

    if args.world:
        model = YOLO(args.world_weights)
        prompts = list(PROMPTS)
        model.set_classes(prompts)
        to_cls = [PROMPTS[p] for p in prompts]
    else:
        model = YOLO(str(ROOT / args.model) if not Path(args.model).is_absolute() else args.model)
        to_cls = list(range(len(CLASSES)))

    img_dir = ROOT / args.images
    root = ROOT / args.out
    lbl_dir = root / "labels"
    lbl_dir.mkdir(parents=True, exist_ok=True)
    (root / "classes.txt").write_text("\n".join(CLASSES) + "\n")
    done = set() if args.overwrite_reviewed else reviewed_set(root)

    images = sorted(p for p in img_dir.glob("*") if p.suffix.lower() in {".jpg", ".png", ".jpeg"})
    stats = {"images": len(images), "kept_reviewed": 0, "prelabelled": 0, "boxes": 0, "no_box": 0,
             "boxes_per_class": {c: 0 for c in CLASSES}}
    for p in images:
        if p.name in done:
            stats["kept_reviewed"] += 1
            continue
        r = model.predict(str(p), conf=conf, imgsz=args.imgsz, verbose=False)[0]
        kept: list[tuple[int, list[float]]] = []
        for b in sorted(r.boxes, key=lambda b: -float(b.conf)):
            xywhn = [float(v) for v in b.xywhn[0]]
            if any(iou_xywh(xywhn, k[1]) > args.max_iou for k in kept):
                continue   # same object hit by another prompt/class: keep the most confident
            kept.append((to_cls[int(b.cls)], xywhn))
        (lbl_dir / f"{p.stem}.txt").write_text("".join(
            f"{c} " + " ".join(f"{np.clip(v, 0, 1):.6f}" for v in b) + "\n" for c, b in kept))
        stats["prelabelled"] += 1
        stats["boxes"] += len(kept)
        stats["no_box"] += not kept
        for c, _ in kept:
            stats["boxes_per_class"][CLASSES[c]] += 1

    # CVAT "YOLO 1.1" import package (upload the images as task data, then Upload annotations -> YOLO 1.1)
    zpath = root / "cvat_annotations.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("obj.names", "\n".join(CLASSES) + "\n")
        z.writestr("obj.data", f"classes = {len(CLASSES)}\nnames = obj.names\ntrain = train.txt\n")
        z.writestr("train.txt", "".join(f"obj_train_data/{p.name}\n" for p in images))
        for p in images:
            lf = lbl_dir / f"{p.stem}.txt"
            if lf.exists():
                z.write(lf, f"obj_train_data/{lf.name}")
    stats["method"] = "yolo-world zero-shot" if args.world else f"model {args.model}"
    stats["conf"] = conf
    ev = ROOT / "evidence/M1"
    ev.mkdir(parents=True, exist_ok=True)
    tag = "world" if args.world else "model"
    (ev / f"autolabel_{tag}.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
