"""Draw boxes, labels, per-class counts and FPS on a frame."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

import cv2
import numpy as np

from ..detect.base import Detection

PALETTE = [(255, 160, 40), (60, 200, 60), (40, 80, 255), (200, 60, 200), (0, 200, 220)]


def draw(img: np.ndarray, dets: Sequence[Detection], fps: float | None = None,
         extra: Sequence[str] = ()) -> np.ndarray:
    out = img.copy()
    for d in dets:
        c = PALETTE[d.cls % len(PALETTE)]
        x1, y1, x2, y2 = map(int, d.box)
        cv2.rectangle(out, (x1, y1), (x2, y2), c, 2)
        label = f"{d.name} {d.conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), c, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    counts = Counter(d.name for d in dets)
    lines = ([f"FPS {fps:.1f}"] if fps is not None else []) + \
            [f"{k}: {v}" for k, v in sorted(counts.items())] + list(extra)
    if lines:
        h = 20 * len(lines) + 8
        cv2.rectangle(out, (0, 0), (190, h), (0, 0, 0), -1)
        for i, s in enumerate(lines):
            cv2.putText(out, s, (6, 20 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out
