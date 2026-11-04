"""M5 pass/fail inspection of one part: the detector says WHAT is in view, classical vision checks HOW it looks.

Verdicts per frame
  NONE  no part with conf >= conf_threshold in view
  FAIL  lid_missing    an open body (Model 1) without a lid
        lid_not_seated body and lid both in view and overlapping, not recognised as a closed enclosure
        lid_only       a loose lid with no body
        surface_mark   dark mark on the enclosure bigger than any seen on GOOD parts
        chipped_corner outline with a bite out of it (less solid / rectangular than any GOOD part)
  NONE  also when the part touches the image border: not fully in view, judge it on a later frame
  PASS  a closed enclosure that passes every check

The thresholds are calibrated from GOOD parts only (scripts/calibrate_inspection.py -> models/inspection.json),
so the rig decides what "normal" looks like, not hand-picked numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .config import resolve
from .detect.base import Detection

DEFAULT_LIMITS = {"mark_frac_max": 0.02, "rect_fill_min": 0.80, "solidity_min": 0.95}


def _iou(a: tuple, b: tuple) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def part_features(image: np.ndarray, box: tuple[float, float, float, float]) -> dict[str, float] | None:
    """Features of the part inside `box`: dark-mark area fraction, how rectangular the outline is, corner count."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    mx, my = 0.08 * (x2 - x1), 0.08 * (y2 - y1)                 # a little background around the part
    xa, ya, xb, yb = int(max(0, x1 - mx)), int(max(0, y1 - my)), int(min(w, x2 + mx)), int(min(h, y2 + my))
    crop = image[ya:yb, xa:xb]
    if crop.size == 0 or min(crop.shape[:2]) < 20:
        return None
    g = cv2.GaussianBlur(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, bright = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)   # white PLA vs darker background
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < 0.15 * crop.shape[0] * crop.shape[1]:
        return None
    filled = np.zeros_like(bright)
    cv2.drawContours(filled, [c], -1, 255, -1)                   # the part including any dark mark on it
    k = max(3, int(0.04 * min(crop.shape[:2])))
    inner = cv2.erode(filled, np.ones((k, k), np.uint8))         # ignore the shaded rim
    part_px = g[inner > 0]
    if part_px.size < 50:
        return None
    dark = ((g < 0.6 * np.median(part_px)) & (inner > 0)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(dark)
    blobs, slot = [], 0
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]
        if a < 4:
            continue
        (_, _), (bw, bh), _ = cv2.minAreaRect(np.column_stack(np.nonzero(lab == i)).astype(np.float32))
        long_, short = max(bw, bh) + 1, min(bw, bh) + 1
        if long_ / short >= 3.5 and a / (long_ * short) >= 0.55:   # long thin box = the designed slot, not a mark
            slot += a
            continue
        blobs.append(a)
    blobs.sort(reverse=True)
    rect_area = cv2.minAreaRect(c)[1][0] * cv2.minAreaRect(c)[1][1]
    hull_area = cv2.contourArea(cv2.convexHull(c))
    return {"mark_frac": float(blobs[0] / part_px.size) if blobs else 0.0,
            "dark_blobs": float(sum(b > 0.001 * part_px.size for b in blobs)),
            "slot_frac": float(slot / part_px.size),
            "rect_fill": float(area / rect_area) if rect_area else 0.0,
            "solidity": float(area / hull_area) if hull_area else 0.0}


@dataclass
class Inspector:
    conf_threshold: float = 0.6
    limits: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    calibrated: bool = False

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Inspector":
        ic = cfg.get("inspection", {})
        path = resolve(ic.get("model_path", "models/inspection.json"))
        limits, calibrated = dict(DEFAULT_LIMITS), False
        if path.exists():
            limits.update(json.loads(path.read_text())["limits"])
            calibrated = True
        return cls(cfg["decide"].get("conf_threshold", 0.6), limits, calibrated)

    def __call__(self, image: np.ndarray, dets: list[Detection]) -> dict[str, Any]:
        good = [d for d in dets if d.conf >= self.conf_threshold]
        if not good:
            return {"verdict": "NONE", "reasons": []}
        enc = [d for d in good if d.name == "enclosure"]
        body = [d for d in good if d.name == "body"]
        lid = [d for d in good if d.name == "lid"]
        if not enc:
            if body and lid and any(_iou(b.box, l.box) > 0.05 for b in body for l in lid):
                return {"verdict": "FAIL", "reasons": ["lid_not_seated"], "part": "body+lid"}
            if body:
                return {"verdict": "FAIL", "reasons": ["lid_missing"], "part": "body"}
            return {"verdict": "FAIL", "reasons": ["lid_only"], "part": "lid"}
        part = max(enc, key=lambda d: d.conf)
        h, w = image.shape[:2]
        x1, y1, x2, y2 = part.box
        if x1 <= 2 or y1 <= 2 or x2 >= w - 3 or y2 >= h - 3:
            return {"verdict": "NONE", "reasons": ["not_fully_in_view"], "part": "enclosure"}
        f = part_features(image, part.box)
        if f is None:
            return {"verdict": "FAIL", "reasons": ["unreadable"], "part": "enclosure"}
        reasons = []
        if f["mark_frac"] > self.limits["mark_frac_max"]:
            reasons.append("surface_mark")
        if f["solidity"] < self.limits["solidity_min"] or f["rect_fill"] < self.limits["rect_fill_min"]:
            reasons.append("chipped_corner")
        return {"verdict": "FAIL" if reasons else "PASS", "reasons": reasons, "part": "enclosure",
                "features": {k: round(v, 4) for k, v in f.items()}}


def make_inspector(cfg: dict[str, Any]) -> Inspector:
    return Inspector.from_config(cfg)
