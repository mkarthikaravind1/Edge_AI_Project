"""M2.4: fair model benchmark - batch 1, 20 warm-up runs, >= 100 timed runs, same input images for every backend.

Two timings per run:
  infer_ms  - the runtime call only (session.run / interpreter.invoke / model forward)
  total_ms  - detect() end to end: letterbox + inference + decode + NMS (what the live pipeline pays)

    python scripts/benchmark_model.py --backend onnx_fp32
    python scripts/benchmark_model.py --backend tflite_int8 --runs 200 --threads 4
-> evidence/M2/benchmark_<host>_<backend>.json
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from edgevision.detect import OnnxDetector, TfliteDetector, UltralyticsDetector
from edgevision.evidence import write_json
from edgevision.hostinfo import host_tag, soc_temperature_c
from edgevision.pipeline import summarise_ms

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
MODELS = {
    "pytorch_fp32": "models/best.pt",
    "onnx_fp32": "models/best.onnx",
    "onnx_int8": "models/best_int8.onnx",
    "tflite_fp32": "models/best_fp32.tflite",
    "tflite_fp16": "models/best_fp16.tflite",
    "tflite_int8": "models/best_int8.tflite",
    "tflite_int8_full": "models/best_int8_full.tflite",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=list(MODELS), required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--tag", default=None, help="host tag in the file name (default laptop / pi)")
    args = ap.parse_args()

    model = args.model or MODELS[args.backend]
    path = ROOT / model
    kw = {"imgsz": args.imgsz, "conf": 0.25, "iou": 0.45}
    if args.backend == "pytorch_fp32":
        import torch

        torch.set_num_threads(args.threads)
        det = UltralyticsDetector(str(path), CLASSES, **kw)
    elif args.backend in ("onnx_fp32", "onnx_int8"):
        det = OnnxDetector(str(path), CLASSES, threads=args.threads, **kw)
    else:
        det = TfliteDetector(str(path), CLASSES, threads=args.threads, **kw)

    imgs = [cv2.imread(str(p)) for p in sorted((ROOT / "data/splits/test/images").glob("*.jpg"))]
    for i in range(args.warmup):
        det.detect(imgs[i % len(imgs)])
    infer, total = [], []
    t_start = time.perf_counter()
    temp_start = soc_temperature_c()
    for i in range(args.runs):
        t = time.perf_counter()
        det.detect(imgs[i % len(imgs)])
        total.append(time.perf_counter() - t)
        infer.append(det.last_infer_s)
    wall = time.perf_counter() - t_start
    tag = args.tag or host_tag()
    res = {
        "backend": args.backend, "model": model, "model_size_mb": round(path.stat().st_size / 1e6, 3),
        "imgsz": args.imgsz, "batch": 1, "threads": args.threads, "warmup_runs": args.warmup, "timed_runs": args.runs,
        "inputs": "real test images, cycled",
        "infer": summarise_ms(infer), "total": summarise_ms(total),
        "fps_infer_median": round(1000 / summarise_ms(infer)["median_ms"], 1),
        "fps_total": round(args.runs / wall, 1),
        "temp_c_start": temp_start, "temp_c_end": soc_temperature_c(),
    }
    out = write_json("M2", f"benchmark_{tag}_{args.backend}", res)
    print(f"{args.backend}: infer median {res['infer']['median_ms']} ms p95 {res['infer']['p95_ms']} ms | "
          f"total median {res['total']['median_ms']} ms | {res['fps_total']} FPS | {res['model_size_mb']} MB -> {out.name}")


if __name__ == "__main__":
    main()
