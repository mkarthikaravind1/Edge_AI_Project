"""FPS and latency meters."""

from __future__ import annotations

import time
from collections import deque

import numpy as np


class FpsMeter:
    """FPS over a sliding time window."""

    def __init__(self, window_s: float = 2.0) -> None:
        self._t: deque[float] = deque()
        self._w = window_s

    def tick(self, t: float | None = None) -> float:
        t = time.perf_counter() if t is None else t
        self._t.append(t)
        while self._t and t - self._t[0] > self._w:
            self._t.popleft()
        return self.fps

    @property
    def fps(self) -> float:
        if len(self._t) < 2:
            return 0.0
        return (len(self._t) - 1) / (self._t[-1] - self._t[0])


def summarise_ms(samples_s: list[float] | np.ndarray) -> dict[str, float]:
    a = np.asarray(samples_s, dtype=float) * 1000.0
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mean_ms": round(float(a.mean()), 3),
        "median_ms": round(float(np.median(a)), 3),
        "p95_ms": round(float(np.percentile(a, 95)), 3),
        "min_ms": round(float(a.min()), 3),
        "max_ms": round(float(a.max()), 3),
        "std_ms": round(float(a.std()), 3),
    }
