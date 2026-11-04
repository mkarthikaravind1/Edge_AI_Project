"""Decision logic: N-of-M debounce, cooldown, and camera-loss safe state.

Pure Python, no hardware imports, so it is unit-tested on the laptop and runs unchanged on the Pi.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Sequence

from ..detect.base import Detection


class Debounce:
    """Fires when at least n of the last m frames were 'hits'. One bad frame alone never fires."""

    def __init__(self, n: int, m: int) -> None:
        if not 1 <= n <= m:
            raise ValueError("need 1 <= n <= m")
        self.n, self.m = n, m
        self._win: deque[bool] = deque(maxlen=m)

    def update(self, hit: bool) -> bool:
        self._win.append(hit)
        return sum(self._win) >= self.n

    def reset(self) -> None:
        self._win.clear()

    @property
    def hits(self) -> int:
        return sum(self._win)


class Event(str, Enum):
    NONE = "none"
    TRIGGER = "trigger"
    COOLDOWN = "cooldown"          # condition true but still within cooldown
    HOLD = "hold"                  # condition true but the part that already fired has not left yet
    SAFE_STATE = "safe_state"      # camera lost
    RECOVERED = "recovered"        # camera back


@dataclass
class Decision:
    event: Event
    hit: bool
    hits_in_window: int
    t: float


class DecisionEngine:
    """input: detections per frame -> output: Decision. Actions are done by the caller via callbacks."""

    def __init__(self, trigger_classes: Sequence[str], conf_threshold: float, n: int, m: int,
                 cooldown_s: float, camera_timeout_s: float, rearm_on_clear: bool = True,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self.trigger_classes = set(trigger_classes)
        self.conf_threshold = conf_threshold
        self.debounce = Debounce(n, m)
        self.cooldown_s = cooldown_s
        self.camera_timeout_s = camera_timeout_s
        self._clock = clock
        self._last_trigger = -1e9
        self._last_frame = clock()
        self.safe = False
        # one trigger per part: after firing, wait until M frames in a row had no hit (part has left)
        self.rearm_on_clear = rearm_on_clear
        self.armed = True
        self._clear_run = 0

    @classmethod
    def from_config(cls, cfg: dict[str, Any], **kw: Any) -> "DecisionEngine":
        return cls(cfg["trigger_classes"], cfg["conf_threshold"], cfg["n"], cfg["m"],
                   cfg["cooldown_s"], cfg["camera_timeout_s"], cfg.get("rearm_on_clear", True), **kw)

    def is_hit(self, dets: Sequence[Detection]) -> bool:
        return any(d.name in self.trigger_classes and d.conf >= self.conf_threshold for d in dets)

    def on_frame(self, dets: Sequence[Detection]) -> Decision:
        return self.on_hit(self.is_hit(dets))

    def on_hit(self, hit: bool) -> Decision:
        """Same N-of-M / cooldown / recovery logic for any per-frame yes/no (detection, or M5 FAIL verdict)."""
        now = self._clock()
        self._last_frame = now
        if self.safe:
            self.safe = False
            self.debounce.reset()
            return Decision(Event.RECOVERED, False, 0, now)
        self._clear_run = 0 if hit else self._clear_run + 1
        if not self.armed and self._clear_run >= self.debounce.m:
            self.armed = True
        fire = self.debounce.update(hit)
        if fire:
            if self.rearm_on_clear and not self.armed:
                return Decision(Event.HOLD, hit, self.debounce.hits, now)
            if now - self._last_trigger >= self.cooldown_s:
                self._last_trigger = now
                self.armed = False
                self.debounce.reset()      # need a fresh N-of-M before the next trigger
                return Decision(Event.TRIGGER, hit, self.debounce.n, now)
            return Decision(Event.COOLDOWN, hit, self.debounce.hits, now)
        return Decision(Event.NONE, hit, self.debounce.hits, now)

    def check_camera(self) -> Decision | None:
        """Call periodically (watchdog). Returns SAFE_STATE once when frames stop arriving."""
        now = self._clock()
        if not self.safe and now - self._last_frame > self.camera_timeout_s:
            self.safe = True
            self.debounce.reset()
            return Decision(Event.SAFE_STATE, False, 0, now)
        return None
