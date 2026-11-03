"""M1.6: find the worst wrong detections on the test set and save them as images + a table.

Error types (matched greedily at IoU >= 0.5):
  FP     - a box where there is no object
  FN     - an object the model missed
  CLASS  - right place, wrong class (body <-> lid)
  LOC    - right class, but the box is poorly placed (0.1 <= IoU < 0.5)

    python scripts/wrong_detections.py --model models/best.pt --data data/splits --n 10
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HINTS = {
    "FP": ("background texture/shape resembles the part", "add hard-negative frames of that background; raise conf threshold"),
    "FN": ("part too small, blurred, dark or heavily occluded", "add frames at that distance/lighting; lower conf or use imgsz 640"),
    "CLASS": ("lid and body look alike from this viewpoint (thin edge-on view)", "add more edge-on views of both parts; check labels"),
    "LOC": ("box covers only part of the object or includes shadow", "tighten labels; add more examples of this pose"),
}


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def load_gt(lbl: Path, w: int, h: int) -> list[tuple[int, np.ndarray]]:
    out = []
    if lbl.exists():
        for line in lbl.read_text().splitlines():
            if line.strip():
                c, x, y, bw, bh = map(float, line.split())
                out.append((int(c), np.array([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h])))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/best.pt")
    ap.add_argument("--data", default="data/splits")
    ap.add_argument("--split", default="test")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="evidence/M1/wrong_detections")
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(ROOT / args.model) if not Path(args.model).is_absolute() else args.model)
    names = model.names
    img_dir = ROOT / args.data / args.split / "images"
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    errors = []
    for p in sorted(img_dir.glob("*.jpg")):
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        gt = load_gt(p.parent.parent / "labels" / f"{p.stem}.txt", w, h)
        r = model.predict(img, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
        preds = [(int(b.cls), float(b.conf), b.xyxy[0].cpu().numpy()) for b in r.boxes]
        used = set()
        for pc, conf, pb in sorted(preds, key=lambda x: -x[1]):
            best_j, best_iou = -1, 0.0
            for j, (gc, gb) in enumerate(gt):
                if j in used:
                    continue
                v = iou(pb, gb)
                if v > best_iou:
                    best_j, best_iou = j, v
            if best_iou >= 0.5:
                used.add(best_j)
                if gt[best_j][0] != pc:
                    errors.append(("CLASS", p, pc, gt[best_j][0], conf, best_iou, pb, gt[best_j][1]))
            elif best_iou >= 0.1 and gt[best_j][0] == pc:
                used.add(best_j)
                errors.append(("LOC", p, pc, pc, conf, best_iou, pb, gt[best_j][1]))
            else:
                errors.append(("FP", p, pc, None, conf, best_iou, pb, None))
        for j, (gc, gb) in enumerate(gt):
            if j not in used:
                errors.append(("FN", p, None, gc, 0.0, 0.0, None, gb))

    # most "confident" mistakes first: FP/CLASS by confidence, then FN, then LOC
    rank = {"CLASS": 0, "FP": 1, "FN": 2, "LOC": 3}
    errors.sort(key=lambda e: (rank[e[0]], -e[4]))
    rows = []
    for k, (kind, p, pc, gc, conf, v, pb, gb) in enumerate(errors[: args.n], 1):
        img = cv2.imread(str(p))
        if gb is not None:
            cv2.rectangle(img, tuple(map(int, gb[:2])), tuple(map(int, gb[2:])), (0, 255, 0), 2)
            cv2.putText(img, f"GT {names[gc]}", (int(gb[0]), int(gb[3]) + 16), 0, 0.55, (0, 255, 0), 2)
        if pb is not None:
            cv2.rectangle(img, tuple(map(int, pb[:2])), tuple(map(int, pb[2:])), (0, 0, 255), 2)
            cv2.putText(img, f"PRED {names[pc]} {conf:.2f}", (int(pb[0]), int(pb[1]) - 6), 0, 0.55, (0, 0, 255), 2)
        cv2.putText(img, kind, (8, 28), 0, 0.9, (0, 255, 255), 2)
        fn = f"{k:02d}_{kind}_{p.stem}.jpg"
        cv2.imwrite(str(out / fn), img)
        why, fix = HINTS[kind]
        rows.append({"#": k, "image": fn, "error": kind, "predicted": names[pc] if pc is not None else "-",
                     "truth": names[gc] if gc is not None else "-", "conf": round(conf, 3), "iou": round(v, 3),
                     "why (edit after looking)": why, "fix": fix})

    with open(out / "wrong_detections.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["#"])
        wr.writeheader()
        wr.writerows(rows)
    md = ["| # | image | error | pred | truth | conf | IoU | why | fix |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['#']} | {r['image']} | {r['error']} | {r['predicted']} | {r['truth']} | {r['conf']} | {r['iou']} | "
           f"{r['why (edit after looking)']} | {r['fix']} |" for r in rows]
    (out / "wrong_detections.md").write_text("\n".join(md) + "\n")
    counts = {k: sum(e[0] == k for e in errors) for k in rank}
    (out / "summary.json").write_text(json.dumps({"total_errors": len(errors), "by_type": counts}, indent=2))
    print(json.dumps(counts), f"-> {out}")


if __name__ == "__main__":
    main()
