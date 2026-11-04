"""The station runtime: camera -> detect -> (inspect) -> decide -> act, plus a camera watchdog.

Threads
  loop      reads frames, runs the detector, feeds the decision engine, fires the reject output
  watchdog  every 50 ms: no frame for camera_timeout_s -> SAFE STATE (run_permit off = conveyor stop)

Everything that happens is published on the EventBus ("frame", "decision", "status"), so MQTT, the dashboard,
the PLC link and the logs are plug-ins that the loop never has to know about.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter, deque
from typing import Any, Callable

import numpy as np

from .bus import EventBus
from .decide import DecisionEngine, Event
from .detect.base import Detection, Detector
from .hal.actuator import Actuator
from .hal.camera import Camera, Frame
from .hal.plc import Plc
from .pipeline import FpsMeter, draw

log = logging.getLogger(__name__)
Inspector = Callable[[np.ndarray, list[Detection]], dict[str, Any]]


class StationRuntime:
    def __init__(self, cfg: dict[str, Any], camera: Camera, detector: Detector, reject: Actuator,
                 run_permit: Actuator, plc: Plc | None = None, bus: EventBus | None = None,
                 inspector: Inspector | None = None, camera_factory: Callable[[], Camera] | None = None,
                 keep_annotated: bool = True) -> None:
        d = cfg["decide"]
        self.cfg = cfg
        self.device_id = cfg.get("device_id", "edge")
        self.camera, self.detector = camera, detector
        self.reject, self.run_permit = reject, run_permit
        self.plc = plc
        self.bus = bus or EventBus()
        self.inspector = inspector
        self.camera_factory = camera_factory
        self.keep_annotated = keep_annotated
        self.engine = DecisionEngine.from_config(d)
        self.pulse_s = d.get("pulse_s", 0.5)
        self.plc_cfg = cfg.get("plc", {})

        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._window: deque[tuple[float, bool]] = deque(maxlen=d["m"])
        self.fps = FpsMeter()
        self.started = 0.0
        self.frames = 0
        self.errors: Counter = Counter()
        self.triggers = 0
        self.safe_events = 0
        self.latencies: list[dict[str, float]] = []        # one per trigger
        self.class_counts: Counter = Counter()
        self.last_dets: list[Detection] = []
        self.last_verdict: dict[str, Any] | None = None
        self.last_annotated: np.ndarray | None = None
        self.last_frame_t = 0.0
        self.state = "starting"

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self.started = time.perf_counter()
        self.engine._last_frame = self.engine._clock()      # give the camera its timeout from now
        for target, name in ((self._loop, "loop"), (self._watchdog, "watchdog")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=3)
        self.run_permit.set(False, "shutdown")
        self.reject.set(False, "shutdown")
        self.state = "stopped"
        self._status()

    def run_for(self, seconds: float) -> None:
        self.start()
        try:
            self._stop.wait(seconds)
        finally:
            self.stop()

    # ------------------------------------------------------------------ threads
    def _loop(self) -> None:
        misses, last_reopen = 0, 0.0
        while not self._stop.is_set():
            try:
                fr = self.camera.read()
            except Exception:
                self.errors["camera_exception"] += 1
                fr = None
            if fr is None:
                misses += 1
                if self.camera_factory and misses > 30 and time.perf_counter() - last_reopen > 2.0:
                    last_reopen = time.perf_counter()
                    self._reopen_camera()
                time.sleep(0.01)
                continue
            misses = 0
            try:
                self._process(fr)
            except Exception:
                self.errors["process_exception"] += 1
                log.exception("frame processing failed")

    def _watchdog(self) -> None:
        last_status = 0.0
        while not self._stop.wait(0.05):
            dec = self.engine.check_camera()
            if dec and dec.event == Event.SAFE_STATE:
                t = self.run_permit.set(False, "SAFE STATE: camera lost")
                self.safe_events += 1
                self.state = "SAFE_STATE"
                log.warning("camera lost for > %.2fs -> safe state (run_permit off)", self.engine.camera_timeout_s)
                self.bus.publish("decision", {"event": "safe_state", "t": t, "reason": "camera lost",
                                              "since_last_frame_s": round(t - self.last_frame_t, 3)})
                self._status()
            if time.perf_counter() - last_status > 1.0:
                last_status = time.perf_counter()
                self._status()

    def _reopen_camera(self) -> None:
        try:
            self.camera.close()
        except Exception:
            pass
        try:
            self.camera = self.camera_factory()
            log.info("camera reopened")
        except Exception:
            self.errors["camera_reopen_failed"] += 1

    # ------------------------------------------------------------------ per frame
    def _process(self, fr: Frame) -> None:
        dets = self.detector.detect(fr.image)
        self.frames += 1
        self.last_frame_t = time.perf_counter()
        fps = self.fps.tick()
        self.last_dets = dets
        for d in dets:
            self.class_counts[d.name] += 1

        if self.inspector is not None:
            verdict = self.inspector(fr.image, dets)
            self.last_verdict = verdict
            hit = verdict.get("verdict") == "FAIL"
        else:
            hit = self.engine.is_hit(dets)
        self._window.append((fr.t_capture, hit))
        dec = self.engine.on_hit(hit)

        if dec.event == Event.RECOVERED:
            self.run_permit.set(True, "camera recovered")
            self.state = "running"
            self.bus.publish("decision", {"event": "recovered", "t": dec.t})
        elif self.state == "starting":
            self.run_permit.set(True, "first frame: healthy")
            self.state = "running"
        elif dec.event == Event.TRIGGER:
            self._trigger(fr, dets)

        if self.keep_annotated:
            extra = [self.state]
            if self.last_verdict:
                extra.append(f"{self.last_verdict.get('verdict')}")
            self.last_annotated = draw(fr.image, dets, fps, extra)
        self.bus.publish("frame", {"index": fr.index, "t_capture": fr.t_capture, "fps": round(fps, 2),
                                   "detections": [d.to_dict() for d in dets], "hit": hit,
                                   "verdict": self.last_verdict, "event": dec.event.value,
                                   "infer_ms": round(self.detector.last_infer_s * 1000, 2)})

    def _trigger(self, fr: Frame, dets: list[Detection]) -> None:
        t_cmd = self.reject.pulse(self.pulse_s, "decision rule fired")
        self.triggers += 1
        first_hit = next((t for t, h in self._window if h), fr.t_capture)
        lat = {"frame_to_cmd_ms": round((t_cmd - fr.t_capture) * 1000, 2),
               "first_hit_to_cmd_ms": round((t_cmd - first_hit) * 1000, 2)}
        self.latencies.append(lat)
        if self.plc is not None:
            try:
                self.plc.write_coil(self.plc_cfg.get("coil", 0), True)
                reg = self.plc_cfg.get("register", 0)
                self.plc.write_register(reg, self.triggers)
                threading.Timer(self.pulse_s, self._plc_coil_off).start()
            except Exception:
                self.errors["plc_write_failed"] += 1
        self.bus.publish("decision", {"event": "trigger", "t": t_cmd, "count": self.triggers,
                                      "detections": [d.to_dict() for d in dets], "verdict": self.last_verdict, **lat})

    def _plc_coil_off(self) -> None:
        try:
            self.plc.write_coil(self.plc_cfg.get("coil", 0), False)
        except Exception:
            self.errors["plc_write_failed"] += 1

    # ------------------------------------------------------------------ status
    def stats(self) -> dict[str, Any]:
        up = time.perf_counter() - self.started if self.started else 0.0
        return {"device_id": self.device_id, "state": self.state, "uptime_s": round(up, 1), "frames": self.frames,
                "fps": round(self.fps.fps, 2), "triggers": self.triggers, "safe_events": self.safe_events,
                "errors": dict(self.errors), "run_permit": self.run_permit.state, "reject": self.reject.state,
                "class_counts": dict(self.class_counts)}

    def _status(self) -> None:
        self.bus.publish("status", self.stats())
