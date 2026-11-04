"""Detector interface shared by all runtimes (PyTorch, ONNX Runtime, TFLite)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass
class Detection:
    cls: int
    name: str
    conf: float
    box: tuple[float, float, float, float]   # x1, y1, x2, y2 in original image pixels

    def to_dict(self) -> dict:
        d = asdict(self)
        d["box"] = [round(v, 1) for v in self.box]
        d["conf"] = round(self.conf, 4)
        return d


class Detector(ABC):
    def __init__(self, names: list[str], imgsz: int = 320, conf: float = 0.25, iou: float = 0.45) -> None:
        self.names = names
        self.imgsz = imgsz
        self.conf = conf
        self.iou = iou
        self.last_infer_s = 0.0      # runtime call only, set by each backend on every detect()

    @abstractmethod
    def detect(self, image: np.ndarray) -> list[Detection]: ...


def letterbox(img: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize keeping aspect ratio and pad to size x size (grey 114, like Ultralytics)."""
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top, left = (size - nh) // 2, (size - nw) // 2
    out = np.full((size, size, 3), 114, np.uint8)
    out[top:top + nh, left:left + nw] = resized
    return out, r, (left, top)


def decode_yolov8(pred: np.ndarray, names: list[str], conf: float, iou: float,
                  scale: float, pad: tuple[int, int], orig_shape: tuple[int, int]) -> list[Detection]:
    """pred: (4 + nc, N) or (N, 4 + nc) with cx, cy, w, h in letterboxed pixels. Applies class-wise NMS."""
    if pred.shape[0] != 4 + len(names) and pred.shape[1] == 4 + len(names):
        pred = pred.T
    boxes, scores = pred[:4].T, pred[4:].T
    cls = scores.argmax(1)
    best = scores[np.arange(len(cls)), cls]
    keep = best >= conf
    if not keep.any():
        return []
    boxes, best, cls = boxes[keep], best[keep], cls[keep]
    x1y1 = boxes[:, :2] - boxes[:, 2:] / 2
    xywh = np.concatenate([x1y1, boxes[:, 2:]], 1)
    out: list[Detection] = []
    h, w = orig_shape
    for c in np.unique(cls):
        m = cls == c
        idx = cv2.dnn.NMSBoxes(xywh[m].tolist(), best[m].tolist(), conf, iou)
        for i in np.array(idx).flatten():
            x, y, bw, bh = xywh[m][i]
            x1 = float(np.clip((x - pad[0]) / scale, 0, w))
            y1 = float(np.clip((y - pad[1]) / scale, 0, h))
            x2 = float(np.clip((x + bw - pad[0]) / scale, 0, w))
            y2 = float(np.clip((y + bh - pad[1]) / scale, 0, h))
            name = names[int(c)] if int(c) < len(names) else str(int(c))
            out.append(Detection(int(c), name, float(best[m][i]), (x1, y1, x2, y2)))
    return sorted(out, key=lambda d: -d.conf)
