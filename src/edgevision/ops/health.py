"""Health check used after an OTA update (and by the container healthcheck): can this model still do the job?

Pass = the model loads, finds the labelled parts on the committed reference images (data/splits/test) with
recall >= min_recall at IoU 0.5, and the median detect() time is within budget.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..config import ROOT
from ..detect import make_detector


def _gt(lbl: Path, w: int, h: int) -> list[tuple[int, np.ndarray]]:
    out = []
    if lbl.exists():
        for line in lbl.read_text().splitlines():
            if line.strip():
                c, x, y, bw, bh = map(float, line.split())
                out.append((int(c), np.array([(x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h])))
    return out


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def health_check(cfg: dict[str, Any], min_recall: float = 0.9, max_median_ms: float = 500.0,
                 ref_dir: Path | None = None) -> dict[str, Any]:
    ref = ref_dir or ROOT / "data/splits/test"
    res: dict[str, Any] = {"model": cfg["detector"]["model"], "backend": cfg["detector"]["backend"],
                           "min_recall": min_recall, "max_median_ms": max_median_ms}
    try:
        det = make_detector({**cfg["detector"], "conf": max(cfg["detector"].get("conf", 0.25), 0.25)}, cfg["classes"])
    except Exception as e:
        return {**res, "ok": False, "reason": f"model failed to load: {type(e).__name__}: {e}"}
    found = total = 0
    times = []
    for p in sorted((ref / "images").glob("*.jpg")):
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        t = time.perf_counter()
        try:
            dets = det.detect(img)
        except Exception as e:
            return {**res, "ok": False, "reason": f"inference failed: {type(e).__name__}: {e}"}
        times.append((time.perf_counter() - t) * 1000)
        for c, box in _gt(ref / "labels" / f"{p.stem}.txt", w, h):
            total += 1
            found += any(d.cls == c and _iou(np.array(d.box), box) >= 0.5 for d in dets)
    recall = found / total if total else 0.0
    med = float(np.median(times)) if times else float("inf")
    ok = recall >= min_recall and med <= max_median_ms
    reason = "ok" if ok else ("recall too low" if recall < min_recall else "too slow")
    return {**res, "ok": ok, "reason": reason, "reference_images": len(times), "parts": total,
            "recall": round(recall, 3), "median_ms": round(med, 2)}
