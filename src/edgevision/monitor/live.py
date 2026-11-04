"""Live motor monitor: IMU stream -> 1 s windows (every 0.5 s) -> features -> anomaly score -> alert.

Alert rule (debounce, like the vision rule): ALERT when `alert_n` windows in a row score above the threshold;
CLEAR after `alert_n` windows in a row below it. Each window is published on the bus as topic "motor".
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any

import numpy as np

from ..bus import EventBus
from ..hal.imu import Imu
from .anomaly import AnomalyModel
from .features import window_features

log = logging.getLogger(__name__)


class AlertDebounce:
    def __init__(self, n: int) -> None:
        self.n, self.above, self.below, self.alert = n, 0, 0, False

    def update(self, is_anomaly: bool) -> str | None:
        """Returns 'alert' / 'clear' on a change, else None."""
        self.above = self.above + 1 if is_anomaly else 0
        self.below = 0 if is_anomaly else self.below + 1
        if not self.alert and self.above >= self.n:
            self.alert = True
            return "alert"
        if self.alert and self.below >= self.n:
            self.alert = False
            return "clear"
        return None


def score_run(model: AnomalyModel, data: np.ndarray, rate_hz: float, window_s: float, step_s: float,
              alert_n: int) -> dict[str, Any]:
    """Offline version of the live loop for a whole recorded run (data: samples x 6)."""
    size, step = int(window_s * rate_hz), int(step_s * rate_hz)
    feats = [window_features(data[i:i + size], rate_hz) for i in range(0, len(data) - size + 1, step)]
    scores = model.score(np.array(feats)) if feats else np.array([])
    deb, alerts, first_alert = AlertDebounce(alert_n), 0, None
    for k, s in enumerate(scores):
        if deb.update(bool(s > model.threshold)) == "alert":
            alerts += 1
            if first_alert is None:
                first_alert = round((k * step + size) / rate_hz, 2)
    return {"windows": len(scores), "windows_above": int((scores > model.threshold).sum()),
            "alerts": alerts, "first_alert_s": first_alert,
            "score_median": round(float(np.median(scores)), 3) if len(scores) else None,
            "score_max": round(float(scores.max()), 3) if len(scores) else None, "scores": scores}


class MotorMonitor:
    def __init__(self, imu: Imu, model: AnomalyModel, cfg: dict[str, Any], bus: EventBus,
                 device_id: str = "edge") -> None:
        a = cfg.get("anomaly", {})
        self.imu, self.model, self.bus = imu, model, bus
        self.rate = cfg.get("imu", {}).get("rate_hz", 200)
        self.size = int(a.get("window_s", 1.0) * self.rate)
        self.step = int(a.get("step_s", 0.5) * self.rate)
        self.deb = AlertDebounce(a.get("alert_n", 2))
        self.device_id = device_id
        self.last: dict[str, Any] = {"score": None, "threshold": model.threshold, "alert": False}
        self.alerts = 0
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def start(self) -> None:
        self._t = threading.Thread(target=self._run, name="motor", daemon=True)
        self._t.start()

    def stop(self) -> None:
        self._stop.set()
        if self._t:
            self._t.join(timeout=3)

    def _run(self) -> None:
        buf: deque[list[float]] = deque(maxlen=self.size)
        since = 0
        for s in self.imu.stream(self.rate):
            if self._stop.is_set():
                break
            buf.append(s.as_row()[1:])
            since += 1
            if len(buf) == self.size and since >= self.step:
                since = 0
                score = float(self.model.score(window_features(np.array(buf), self.rate))[0])
                change = self.deb.update(score > self.model.threshold)
                if change == "alert":
                    self.alerts += 1
                    log.warning("MOTOR ANOMALY: score %.2f > threshold %.2f", score, self.model.threshold)
                self.last = {"device_id": self.device_id, "t": time.time(), "score": round(score, 3),
                             "threshold": round(self.model.threshold, 3), "alert": self.deb.alert,
                             "change": change, "alerts_total": self.alerts}
                self.bus.publish("motor", self.last)
        log.info("motor monitor stopped")
