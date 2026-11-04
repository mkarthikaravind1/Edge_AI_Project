"""Camera HAL. Core code only sees Camera.read(); the backend is picked from config."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class Frame:
    image: np.ndarray        # BGR, HxWx3
    t_capture: float         # time.perf_counter() at capture
    index: int


class CameraError(RuntimeError):
    pass


class Camera(ABC):
    def __init__(self) -> None:
        self._index = 0

    @abstractmethod
    def _grab(self) -> np.ndarray | None: ...

    def read(self) -> Frame | None:
        """Returns None when no frame is available (camera unplugged, end of video)."""
        img = self._grab()
        if img is None:
            return None
        self._index += 1
        return Frame(img, time.perf_counter(), self._index)

    def close(self) -> None:
        pass

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class WebcamCamera(Camera):
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30) -> None:
        super().__init__()
        import cv2

        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        if not self._cap.isOpened():
            raise CameraError(f"cannot open webcam {index}")

    def _grab(self) -> np.ndarray | None:
        ok, img = self._cap.read()
        return img if ok else None

    def close(self) -> None:
        self._cap.release()


class VideoFileCamera(Camera):
    """Plays a video file as if it were a camera. realtime=True paces frames at the file's FPS."""

    def __init__(self, path: str, loop: bool = True, realtime: bool = False,
                 width: int | None = None, height: int | None = None) -> None:
        super().__init__()
        import cv2

        self._cv2 = cv2
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise CameraError(f"cannot open video {path}")
        self._loop = loop
        self._size = (width, height) if width and height else None
        self._period = 1.0 / (self._cap.get(cv2.CAP_PROP_FPS) or 30.0) if realtime else 0.0
        self._next = time.perf_counter()

    def _grab(self) -> np.ndarray | None:
        if self._period:
            delay = self._next - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            self._next = max(self._next + self._period, time.perf_counter())
        ok, img = self._cap.read()
        if not ok and self._loop:
            self._cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ok, img = self._cap.read()
        if not ok:
            return None
        if self._size:
            img = self._cv2.resize(img, self._size)
        return img

    def close(self) -> None:
        self._cap.release()


class FakeCamera(Camera):
    """Synthetic frames for tests. fail_after=N simulates the camera dying after N frames."""

    def __init__(self, width: int = 640, height: int = 480, fail_after: int | None = None) -> None:
        super().__init__()
        self._shape = (height, width, 3)
        self._fail_after = fail_after

    def _grab(self) -> np.ndarray | None:
        if self._fail_after is not None and self._index >= self._fail_after:
            return None
        img = np.full(self._shape, 40, np.uint8)
        x = (self._index * 7) % (self._shape[1] - 100)
        img[100:200, x:x + 100] = (200, 200, 200)
        return img


class PiCamera2Camera(Camera):
    def __init__(self, width: int = 640, height: int = 480, fps: int = 30) -> None:
        super().__init__()
        from picamera2 import Picamera2  # only installed on the Pi

        self._cam = Picamera2()
        cfg = self._cam.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameRate": fps},
        )
        self._cam.configure(cfg)
        self._cam.start()

    def _grab(self) -> np.ndarray | None:
        try:
            # Picamera2 "RGB888" is already BGR byte order in memory, which OpenCV expects.
            return self._cam.capture_array("main")
        except Exception:
            return None

    def close(self) -> None:
        self._cam.stop()
        self._cam.close()


def make_camera(cfg: dict[str, Any], realtime: bool = True) -> Camera:
    from ..config import resolve

    kind = cfg.get("type", "webcam")
    w, h = cfg.get("width", 640), cfg.get("height", 480)
    if kind == "webcam":
        return WebcamCamera(cfg.get("index", 0), w, h, cfg.get("fps", 30))
    if kind == "video":
        # keep the file's own size/aspect unless the config explicitly asks to resize it
        rs = cfg.get("resize_video", False)
        return VideoFileCamera(str(resolve(cfg["path"])), cfg.get("loop", True), realtime,
                               w if rs else None, h if rs else None)
    if kind == "picamera2":
        return PiCamera2Camera(w, h, cfg.get("fps", 30))
    if kind == "fake":
        return FakeCamera(w, h, cfg.get("fail_after"))
    raise ValueError(f"unknown camera type {kind}")
