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


def resolve_webcam(index: int | str = 0) -> int | str:
    """Which device to open for a USB webcam.

    "auto" (Linux / Raspberry Pi): the first /dev/v4l/by-id/*-video-index0 link. That name stays the same when the
    webcam is unplugged and plugged back in, while the /dev/videoN number can change (video0 -> video2), so the
    camera-unplug test (M3 safe state) recovers on the same camera. Elsewhere, or if no link exists: index 0.
    A number or a device path is used as given.
    """
    if isinstance(index, str) and index != "auto":
        return int(index) if index.isdigit() else index
    if index != "auto":
        return index
    import glob
    links = sorted(glob.glob("/dev/v4l/by-id/*-video-index0"))
    return links[0] if links else 0


class WebcamCamera(Camera):
    """USB webcam through OpenCV. On Linux it uses V4L2 + MJPG, which most USB webcams need for 640x480 at 30 FPS,
    and a 1-frame buffer so the detector always sees the newest frame (lower latency)."""

    def __init__(self, index: int | str = 0, width: int = 640, height: int = 480, fps: int = 30,
                 fourcc: str | None = "MJPG") -> None:
        super().__init__()
        import sys

        import cv2

        dev = resolve_webcam(index)
        if sys.platform.startswith("linux"):
            self._cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
            if fourcc:
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        else:
            self._cap = cv2.VideoCapture(dev)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self._cap.isOpened():
            raise CameraError(f"cannot open webcam {dev}")
        self.device = dev

    def _grab(self) -> np.ndarray | None:
        ok, img = self._cap.read()
        return img if ok else None

    def close(self) -> None:
        self._cap.release()


class ImageFolderCamera(Camera):
    """Loops the images of a folder as if they were a camera (sorted by name). realtime=True delivers them at `fps`.

    Used as the SECOND stream of the two-stream test (M3.2) when only one webcam is connected: the folder holds
    real recorded frames of the part, and the folder is in git, so it exists on the Pi (videos are git-ignored).
    """

    def __init__(self, path: str, fps: float = 30.0, realtime: bool = True,
                 width: int | None = None, height: int | None = None) -> None:
        super().__init__()
        import cv2
        from pathlib import Path

        self._cv2 = cv2
        files = sorted(p for p in Path(path).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}) \
            if Path(path).is_dir() else []
        self._imgs = [im for im in (cv2.imread(str(p)) for p in files) if im is not None]
        if not self._imgs:
            raise CameraError(f"no images in {path}")
        if width and height:
            self._imgs = [cv2.resize(im, (width, height)) for im in self._imgs]
        self._period = 1.0 / fps if realtime and fps else 0.0
        self._next = time.perf_counter()
        self._i = 0

    def _grab(self) -> np.ndarray | None:
        if self._period:
            delay = self._next - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            self._next = max(self._next + self._period, time.perf_counter())
        img = self._imgs[self._i % len(self._imgs)]
        self._i += 1
        return img.copy()


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


class FlakyCamera(Camera):
    """Wraps a camera and simulates an unplugged cable between drop_at_s and resume_at_s (seconds after start)."""

    def __init__(self, inner: Camera, drop_at_s: float, resume_at_s: float | None = None) -> None:
        super().__init__()
        self.inner, self.drop_at, self.resume_at = inner, drop_at_s, resume_at_s
        self._t0 = time.perf_counter()

    def _grab(self) -> np.ndarray | None:
        t = time.perf_counter() - self._t0
        fr = self.inner.read()
        if t >= self.drop_at and (self.resume_at is None or t < self.resume_at):
            time.sleep(0.03)          # a dead camera blocks a little, then returns nothing
            return None
        return None if fr is None else fr.image

    def close(self) -> None:
        self.inner.close()


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
        return WebcamCamera(cfg.get("index", 0), w, h, cfg.get("fps", 30), cfg.get("fourcc", "MJPG"))
    if kind == "images":
        rs = cfg.get("resize_video", False)
        return ImageFolderCamera(str(resolve(cfg["path"])), cfg.get("fps", 30), realtime,
                                 w if rs else None, h if rs else None)
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
