"""KPIs and the headline metric, computed live from the runtime's parts and latencies."""

from __future__ import annotations

import time
from typing import Any

import numpy as np


def kpis(rt: Any, window_s: float = 300.0) -> dict[str, Any]:
    parts = list(rt.parts)
    now = time.time()
    recent = [p for p in parts if now - p.t_end <= window_s]
    span = min(window_s, max(1.0, now - parts[0].t_end)) if parts else window_s
    judged = [p for p in parts if p.result in ("PASS", "FAIL")]
    passed = sum(p.result == "PASS" for p in judged)
    lat = [l["first_hit_to_cmd_ms"] for l in list(rt.latencies)[-200:]]

    labelled = [p for p in judged if p.truth in ("good", "defective")]
    correct = sum((p.result == "PASS") == (p.truth == "good") for p in labelled)
    defective = [p for p in labelled if p.truth == "defective"]
    false_pass = sum(p.result == "PASS" for p in defective)
    return {
        "throughput_per_min": round(len(recent) / (span / 60.0), 2) if recent else 0.0,
        "parts_total": len(parts),
        "yield_pct": round(100.0 * passed / len(judged), 1) if judged else None,
        "median_latency_ms": round(float(np.median(lat)), 1) if lat else None,
        "headline": {"correct": correct, "labelled": len(labelled),
                     "text": f"{correct}/{len(labelled)} correct" if labelled else "label parts to score",
                     "false_pass_rate": round(false_pass / len(defective), 3) if defective else None,
                     "false_pass": false_pass, "defective_labelled": len(defective)},
    }
