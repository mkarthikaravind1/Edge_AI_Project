"""Runtime backends. Each one turns a BGR frame into a list of Detection."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from .base import Detection, Detector, decode_yolov8, letterbox


class UltralyticsDetector(Detector):
    """FP32 PyTorch reference (laptop / evaluation)."""

    def __init__(self, model: str, names: list[str] | None = None, **kw: Any) -> None:
        from ultralytics import YOLO

        self._m = YOLO(model)
        super().__init__(names or list(self._m.names.values()), **kw)

    def detect(self, image: np.ndarray) -> list[Detection]:
        r = self._m.predict(image, imgsz=self.imgsz, conf=self.conf, iou=self.iou, verbose=False)[0]
        self.last_infer_s = r.speed["inference"] / 1000.0
        out = []
        for b in r.boxes:
            c = int(b.cls)
            out.append(Detection(c, self._m.names[c], float(b.conf), tuple(float(v) for v in b.xyxy[0])))
        return out


class OnnxDetector(Detector):
    def __init__(self, model: str, names: list[str], threads: int = 4, **kw: Any) -> None:
        import onnxruntime as ort

        super().__init__(names, **kw)
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        self._s = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
        self._in = self._s.get_inputs()[0].name

    def detect(self, image: np.ndarray) -> list[Detection]:
        lb, r, pad = letterbox(image, self.imgsz)
        x = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        t = time.perf_counter()
        pred = self._s.run(None, {self._in: x})[0][0]
        self.last_infer_s = time.perf_counter() - t
        return decode_yolov8(pred, self.names, self.conf, self.iou, r, pad, image.shape[:2])


def _tflite_interpreter(model: str, threads: int, delegate: str | None) -> Any:
    try:
        from ai_edge_litert.interpreter import Interpreter, load_delegate
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter, load_delegate
        except ImportError:
            import tensorflow as tf

            Interpreter, load_delegate = tf.lite.Interpreter, tf.lite.experimental.load_delegate
    delegates = [load_delegate(delegate)] if delegate else None
    return Interpreter(model_path=model, num_threads=threads, experimental_delegates=delegates)


class TfliteDetector(Detector):
    """INT8 / FP16 TFLite. delegate='libedgetpu.so.1' for a Coral Edge TPU."""

    def __init__(self, model: str, names: list[str], threads: int = 4,
                 delegate: str | None = None, **kw: Any) -> None:
        super().__init__(names, **kw)
        self._it = _tflite_interpreter(model, threads, delegate)
        self._it.allocate_tensors()
        self._inp = self._it.get_input_details()[0]
        self._out = self._it.get_output_details()[0]

    def detect(self, image: np.ndarray) -> list[Detection]:
        lb, r, pad = letterbox(image, self.imgsz)
        rgb = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB)[None]   # NHWC uint8
        if self._inp["dtype"] in (np.int8, np.uint8):
            s, z = self._inp["quantization"]
            info = np.iinfo(self._inp["dtype"])
            if abs(s * 255.0 - 1.0) < 1e-6:
                # scale is exactly 1/255, so q = pixel/255/s + z = pixel + z: integer maths only, no float pass
                x = (rgb.astype(np.int16) + int(z)).clip(info.min, info.max).astype(self._inp["dtype"])
            else:
                x = np.clip(np.round(rgb.astype(np.float32) / 255.0 / s + z), info.min, info.max).astype(self._inp["dtype"])
        else:
            x = rgb.astype(np.float32) / 255.0
        self._it.set_tensor(self._inp["index"], x)
        t = time.perf_counter()
        self._it.invoke()
        self.last_infer_s = time.perf_counter() - t
        y = self._it.get_tensor(self._out["index"])[0]
        if self._out["dtype"] in (np.int8, np.uint8):
            s, z = self._out["quantization"]
            y = (y.astype(np.float32) - z) * s
        if y.shape[0] != 4 + len(self.names):
            y = y.T
        if y[:4].max() <= 2.0:          # Ultralytics TFLite exports normalised xywh
            y = y.copy()
            y[:4] *= self.imgsz
        return decode_yolov8(y, self.names, self.conf, self.iou, r, pad, image.shape[:2])


def make_detector(cfg: dict[str, Any], names: list[str]) -> Detector:
    from ..config import resolve

    backend = cfg.get("backend", "ultralytics")
    model = resolve(cfg["model"])
    kw = {"imgsz": cfg.get("imgsz", 320), "conf": cfg.get("conf", 0.25), "iou": cfg.get("iou", 0.45)}
    if backend == "ultralytics":
        if not model.exists() and cfg.get("fallback_model"):
            print(f"[detector] {model} not found -> using public weights {cfg['fallback_model']} (COCO classes)")
            return UltralyticsDetector(cfg["fallback_model"], None, **kw)
        return UltralyticsDetector(str(model), names, **kw)
    if backend == "onnx":
        return OnnxDetector(str(model), names, cfg.get("threads", 4), **kw)
    if backend == "tflite":
        return TfliteDetector(str(model), names, cfg.get("threads", 4), cfg.get("delegate"), **kw)
    raise ValueError(f"unknown backend {backend}")


__all__ = ["UltralyticsDetector", "OnnxDetector", "TfliteDetector", "make_detector"]
