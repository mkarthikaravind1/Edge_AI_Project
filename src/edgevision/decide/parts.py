"""Turn the per-frame stream into PARTS: one record per part that passes the camera.

A part starts when it is seen (a detection >= conf) and ends after `gap` frames in a row without it. Its result:
  FAIL  the reject rule fired while it was in view (>= N of M frames had a FAIL verdict)
  PASS  inspected (enough PASS frames) and the reject rule never fired
  SEEN  inspection off (M3 mode): the part was just counted
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Part:
    id: int
    t_start: float
    frames: int = 0
    verdicts: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)
    rejected: bool = False
    latency_ms: float | None = None
    result: str = ""
    t_end: float = 0.0
    truth: str | None = None          # set by the operator on the dashboard: "good" / "defective"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "result": self.result, "frames": self.frames, "duration_s": round(self.t_end - self.t_start, 2),
                "verdicts": dict(self.verdicts), "reasons": dict(self.reasons), "rejected": self.rejected,
                "latency_ms": self.latency_ms, "truth": self.truth, "t_end": self.t_end,
                "correct": None if self.truth is None or self.result not in ("PASS", "FAIL")
                else (self.result == "PASS") == (self.truth == "good")}


class PartTracker:
    def __init__(self, gap: int = 5, min_frames: int = 3, inspecting: bool = True,
                 clock=time.time) -> None:
        self.gap, self.min_frames, self.inspecting, self._clock = gap, min_frames, inspecting, clock
        self.current: Part | None = None
        self._absent = 0
        self._next_id = 1

    def update(self, present: bool, verdict: dict[str, Any] | None, triggered: bool,
               latency_ms: float | None = None) -> Part | None:
        """Feed one frame. Returns the finished Part when one has just left the view."""
        if present:
            self._absent = 0
            if self.current is None:
                self.current = Part(self._next_id, self._clock())
                self._next_id += 1
            p = self.current
            p.frames += 1
            if verdict:
                p.verdicts[verdict.get("verdict", "NONE")] += 1
                for r in verdict.get("reasons", []):
                    p.reasons[r] += 1
        elif self.current is not None:
            self._absent += 1
        if triggered and self.current is not None:
            self.current.rejected = True
            self.current.latency_ms = latency_ms
        if self.current is not None and self._absent >= self.gap:
            p, self.current = self.current, None
            if p.frames < self.min_frames:
                return None                       # a glitch, not a part
            p.t_end = self._clock()
            if not self.inspecting:
                p.result = "SEEN"
            elif p.rejected:
                p.result = "FAIL"
            else:
                p.result = "PASS" if p.verdicts["PASS"] >= self.min_frames else "UNSURE"
            return p
        return None
