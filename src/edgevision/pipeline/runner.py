"""Single-stream and two-stream runners: camera -> detector -> callback."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from ..detect.base import Detection, Detector
from ..hal.camera import Camera, Frame
from .meters import FpsMeter

OnResult = Callable[[Frame, list[Detection], float], None]   # frame, detections, fps


@dataclass
class StreamStats:
    name: str
    frames: int = 0
    infer_s: list[float] = field(default_factory=list)
    started: float = 0.0
    ended: float = 0.0
    errors: int = 0

    @property
    def fps(self) -> float:
        dt = self.ended - self.started
        return self.frames / dt if dt > 0 else 0.0


def run_stream(name: str, cam: Camera, det: Detector, on_result: OnResult | None = None,
               max_frames: int | None = None, duration_s: float | None = None,
               stop: threading.Event | None = None, lock: threading.Lock | None = None,
               on_no_frame: Callable[[], bool] | None = None) -> StreamStats:
    """Loop until stop/max_frames/duration. on_no_frame() -> True means keep waiting."""
    st = StreamStats(name, started=time.perf_counter())
    meter = FpsMeter()
    stop = stop or threading.Event()
    while not stop.is_set():
        if max_frames is not None and st.frames >= max_frames:
            break
        if duration_s is not None and time.perf_counter() - st.started >= duration_s:
            break
        fr = cam.read()
        if fr is None:
            if on_no_frame and on_no_frame():
                time.sleep(0.01)
                continue
            break
        t0 = time.perf_counter()
        try:
            if lock:
                with lock:
                    dets = det.detect(fr.image)
            else:
                dets = det.detect(fr.image)
        except Exception:
            st.errors += 1
            continue
        st.infer_s.append(time.perf_counter() - t0)
        st.frames += 1
        fps = meter.tick()
        if on_result:
            on_result(fr, dets, fps)
    st.ended = time.perf_counter()
    return st


def run_two_streams(cams: dict[str, Camera], dets: dict[str, Detector], duration_s: float,
                    shared_lock: bool, on_result: Callable[[str, Frame, list[Detection], float], None] | None = None
                    ) -> dict[str, StreamStats]:
    """One thread per stream. shared_lock=True when both streams share one model instance."""
    lock = threading.Lock() if shared_lock else None
    results: dict[str, StreamStats] = {}
    stop = threading.Event()

    def worker(n: str) -> None:
        cb = (lambda f, d, fps: on_result(n, f, d, fps)) if on_result else None
        results[n] = run_stream(n, cams[n], dets[n], cb, duration_s=duration_s, stop=stop, lock=lock)

    threads = [threading.Thread(target=worker, args=(n,), daemon=True) for n in cams]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results
