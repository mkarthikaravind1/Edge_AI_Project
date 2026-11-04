"""M2.2 (second INT8 path): static INT8 quantisation of models/best.onnx with ONNX Runtime.

Runs on any OS and the result runs on the Pi with onnxruntime. Calibration = images from the TRAIN split only,
pre-processed exactly like the live pipeline (letterbox 320, RGB, /255).
QDQ format, per-channel weights, MinMax calibration; the detection head (Concat/Sigmoid/box decode at the end)
is kept in FP32 because quantising it costs a lot of box accuracy for almost no speed.

    python scripts/quantize_onnx.py                -> models/best_int8.onnx
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import cv2
import numpy as np

from edgevision.detect import letterbox

ROOT = Path(__file__).resolve().parents[1]


def preprocess(path: Path, imgsz: int) -> np.ndarray:
    lb, _, _ = letterbox(cv2.imread(str(path)), imgsz)
    return cv2.cvtColor(lb, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0


def head_nodes(model_path: Path, last_n: int) -> list[str]:
    """Names of the last `last_n` nodes (the decode part of the YOLOv8 head) to keep in FP32."""
    import onnx

    nodes = onnx.load(str(model_path)).graph.node
    return [n.name for n in nodes[-last_n:]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/best.onnx")
    ap.add_argument("--out", default="models/best_int8.onnx")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--calib-n", type=int, default=200)
    ap.add_argument("--keep-fp32-tail", type=int, default=30, help="last N graph nodes left in FP32")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
    from onnxruntime.quantization.shape_inference import quant_pre_process

    imgs = [p for p in sorted((ROOT / "data/splits/train/images").glob("*.jpg")) if not p.stem.startswith("aug_")]
    real = [p for p in imgs if p.stem.startswith("clip")]
    syn = [p for p in imgs if p.stem.startswith("syn_")]
    random.Random(args.seed).shuffle(syn)
    calib = (real + syn)[: args.calib_n] if len(real) < args.calib_n else real[: args.calib_n]
    if len(real) < args.calib_n:
        calib = real + syn[: args.calib_n - len(real)]

    class Reader(CalibrationDataReader):
        def __init__(self) -> None:
            self.it = iter(calib)

        def get_next(self):
            p = next(self.it, None)
            return None if p is None else {"images": preprocess(p, args.imgsz)}

    src = ROOT / args.model
    pre = ROOT / "runs/calib/best_pre.onnx"
    pre.parent.mkdir(parents=True, exist_ok=True)
    quant_pre_process(str(src), str(pre))
    t = time.perf_counter()
    keep = head_nodes(pre, args.keep_fp32_tail)
    quantize_static(str(pre), str(ROOT / args.out), Reader(), quant_format=QuantFormat.QDQ,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8, per_channel=True,
                    nodes_to_exclude=keep)
    dt = time.perf_counter() - t
    out = ROOT / args.out
    ev = ROOT / "evidence/M2/export.json"
    rep = json.loads(ev.read_text()) if ev.exists() else {}
    rep["onnx_int8"] = {"file": args.out, "size_mb": round(out.stat().st_size / 1e6, 3), "method": "onnxruntime quantize_static",
                        "format": "QDQ, weights int8 per-channel, activations uint8, MinMax",
                        "fp32_tail_nodes": args.keep_fp32_tail, "calibration": {"split": "train (no augmented copies)",
                        "images": len(calib), "real": sum(p in real for p in calib), "synthetic": sum(p in syn for p in calib),
                        "seed": args.seed}, "quantize_s": round(dt, 1)}
    ev.write_text(json.dumps(rep, indent=2))
    print(f"{out.name}: {rep['onnx_int8']['size_mb']} MB from {len(calib)} calibration images")


if __name__ == "__main__":
    main()
