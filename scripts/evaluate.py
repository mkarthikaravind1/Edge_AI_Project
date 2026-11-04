"""M2.3: accuracy of FP32 (PyTorch) vs ONNX vs INT8 TFLite on the SAME real images, with ONE metric implementation.

    python scripts/evaluate.py                      # all backends whose model file exists
    python scripts/evaluate.py --backends onnx tflite_int8

mAP: per class, predictions sorted by confidence are matched greedily to ground truth (IoU >= t);
AP = area under the precision-recall curve with 101-point interpolation (COCO style), averaged over
classes; mAP@0.5:0.95 averages that over t = 0.50, 0.55, ..., 0.95.
-> evidence/M2/accuracy_compare.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from edgevision.detect import OnnxDetector, TfliteDetector, UltralyticsDetector

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
IOUS = np.linspace(0.5, 0.95, 10)
BACKENDS = {
    "pytorch_fp32": ("models/best.pt", lambda m, kw: UltralyticsDetector(m, CLASSES, **kw)),
    "onnx_fp32": ("models/best.onnx", lambda m, kw: OnnxDetector(m, CLASSES, **kw)),
    "onnx_int8": ("models/best_int8.onnx", lambda m, kw: OnnxDetector(m, CLASSES, **kw)),
    "tflite_fp32": ("models/best_fp32.tflite", lambda m, kw: TfliteDetector(m, CLASSES, **kw)),
    "tflite_int8": ("models/best_int8.tflite", lambda m, kw: TfliteDetector(m, CLASSES, **kw)),
}


def load_gt(lbl: Path, w: int, h: int) -> list[tuple[int, np.ndarray]]:
    out = []
    if lbl.exists():
        for line in lbl.read_text().splitlines():
            if line.strip():
                c, x, y, bw, bh = map(float, line.split())
                out.append((int(c), np.array([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h])))
    return out


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = lambda r: (r[:, 2] - r[:, 0]) * (r[:, 3] - r[:, 1])
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


def ap101(tp: np.ndarray, conf: np.ndarray, n_gt: int) -> float:
    if n_gt == 0:
        return float("nan")
    if len(tp) == 0:
        return 0.0
    o = np.argsort(-conf)
    tpc = np.cumsum(tp[o])
    fpc = np.cumsum(1 - tp[o])
    rec = tpc / n_gt
    prec = tpc / (tpc + fpc)
    prec = np.maximum.accumulate(prec[::-1])[::-1]          # make precision monotonically decreasing
    pts = np.linspace(0, 1, 101)
    idx = np.searchsorted(rec, pts, side="left")
    return float(np.mean([prec[i] if i < len(prec) else 0.0 for i in idx]))


def evaluate(det, images: list[Path], label_dir: Path, op_conf: float) -> dict:
    stats = {c: {"tp": [], "conf": [], "n_gt": 0} for c in range(len(CLASSES))}
    op = {"tp": 0, "fp": 0, "fn": 0}
    for p in images:
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        gt = load_gt(label_dir / f"{p.stem}.txt", w, h)
        dets = det.detect(img)
        for c in range(len(CLASSES)):
            g = np.array([b for k, b in gt if k == c]).reshape(-1, 4)
            d = [x for x in dets if x.cls == c]
            stats[c]["n_gt"] += len(g)
            d.sort(key=lambda x: -x.conf)
            tp = np.zeros((len(d), len(IOUS)))
            if len(d) and len(g):
                ious = iou_matrix(np.array([x.box for x in d]), g)
                for ti, t in enumerate(IOUS):
                    used = set()
                    for i in range(len(d)):
                        cand = [(ious[i, j], j) for j in range(len(g)) if j not in used and ious[i, j] >= t]
                        if cand:
                            used.add(max(cand)[1])
                            tp[i, ti] = 1
            stats[c]["tp"] += list(tp)
            stats[c]["conf"] += [x.conf for x in d]
            # operating point (conf >= op_conf, IoU 0.5) for precision / recall
            keep = [i for i, x in enumerate(d) if x.conf >= op_conf]
            hits = int(tp[keep, 0].sum()) if keep else 0
            op["tp"] += hits
            op["fp"] += len(keep) - hits
            op["fn"] += len(g) - hits
    per_class, ap50, ap5095 = {}, [], []
    for c, s in stats.items():
        tp = np.array(s["tp"]).reshape(-1, len(IOUS))
        conf = np.array(s["conf"])
        aps = [ap101(tp[:, i], conf, s["n_gt"]) for i in range(len(IOUS))]
        if s["n_gt"]:
            ap50.append(aps[0])
            ap5095.append(float(np.mean(aps)))
        per_class[CLASSES[c]] = {"n_gt": s["n_gt"], "ap50": round(aps[0], 4), "ap50_95": round(float(np.mean(aps)), 4)}
    p = op["tp"] / max(1, op["tp"] + op["fp"])
    r = op["tp"] / max(1, op["tp"] + op["fn"])
    return {"images": len(images), "mAP50": round(float(np.mean(ap50)), 4), "mAP50_95": round(float(np.mean(ap5095)), 4),
            f"precision@{op_conf}": round(p, 4), f"recall@{op_conf}": round(r, 4), **op, "per_class": per_class}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", nargs="+", default=list(BACKENDS))
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--op-conf", type=float, default=0.25, help="confidence for the precision/recall operating point")
    args = ap.parse_args()

    sets = {
        "test_real": sorted((ROOT / "data/splits/test/images").glob("*.jpg")),
        "val_real": sorted((ROOT / "data/splits/val/images").glob("clip*.jpg")),
    }
    out_path = ROOT / "evidence/M2/accuracy_compare.json"
    report = json.loads(out_path.read_text()) if out_path.exists() else {"results": {}}
    report["method"] = __doc__.split("mAP:")[1].split("->")[0].strip()
    report["imgsz"] = args.imgsz
    kw = {"imgsz": args.imgsz, "conf": 0.001, "iou": 0.7}
    for name in args.backends:
        model, make = BACKENDS[name]
        if not (ROOT / model).exists():
            print(f"skip {name}: {model} not found")
            continue
        det = make(str(ROOT / model), kw)
        report["results"][name] = {"model": model, "size_mb": round((ROOT / model).stat().st_size / 1e6, 3)}
        for sname, imgs in sets.items():
            split = "test" if sname == "test_real" else "val"
            report["results"][name][sname] = evaluate(det, imgs, ROOT / f"data/splits/{split}/labels", args.op_conf)
        print(name, {s: (v["mAP50"], v["mAP50_95"]) for s, v in report["results"][name].items() if isinstance(v, dict)})
    base = report["results"].get("pytorch_fp32")
    if base:
        for name, r in report["results"].items():
            r["delta_vs_fp32"] = {s: {"mAP50": round(r[s]["mAP50"] - base[s]["mAP50"], 4),
                                      "mAP50_95": round(r[s]["mAP50_95"] - base[s]["mAP50_95"], 4)}
                                  for s in ("test_real", "val_real") if s in r and s in base}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print("->", out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
