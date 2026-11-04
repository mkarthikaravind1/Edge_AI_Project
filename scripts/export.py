"""M2.1 / M2.2: export my trained model for the edge device.

    python scripts/export.py --format onnx                 -> models/best.onnx          (FP32)
    python scripts/export.py --format tflite --int8        -> models/best_int8.tflite   (full INT8)
    python scripts/export.py --format all

INT8 calibration uses a representative set from the TRAIN split only (real frames + some renders, no augmented
copies), never val/test, so the quantiser has not "seen" the images we later score it on.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]


def calibration_yaml(n: int, seed: int) -> Path:
    imgs = sorted((ROOT / "data/splits/train/images").glob("*.jpg"))
    real = [p for p in imgs if p.stem.startswith("clip")]
    syn = [p for p in imgs if p.stem.startswith("syn_")]
    random.Random(seed).shuffle(syn)
    chosen = (real + syn)[: max(n, len(real))] if len(real) >= n else real + syn[: n - len(real)]
    work = ROOT / "runs/calib"
    work.mkdir(parents=True, exist_ok=True)
    lst = work / "calib.txt"
    lst.write_text("".join(p.resolve().as_posix() + "\n" for p in chosen))
    y = work / "calib.yaml"
    y.write_text(f"path: {work.as_posix()}\ntrain: {lst.as_posix()}\nval: {lst.as_posix()}\nnames:\n"
                 + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    (work / "calib_info.json").write_text(json.dumps({"images": len(chosen), "real": sum(p in real for p in chosen),
                                                      "synthetic": sum(p in syn for p in chosen)}))
    return y


def size_mb(p: Path) -> float:
    return round(p.stat().st_size / 1e6, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="models/best.pt")
    ap.add_argument("--format", choices=["onnx", "tflite", "all"], default="onnx")
    ap.add_argument("--int8", action="store_true", help="tflite: full-integer INT8 with calibration")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--calib-n", type=int, default=200, help="calibration images from the train split")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from ultralytics import YOLO

    weights = ROOT / args.weights
    out_dir = ROOT / "models"
    ev_path = ROOT / "evidence/M2/export.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(ev_path.read_text()) if ev_path.exists() else {}
    report["source"] = {"weights": args.weights, "size_mb": size_mb(weights), "imgsz": args.imgsz}

    if args.format in ("onnx", "all"):
        t = time.perf_counter()
        p = Path(YOLO(str(weights)).export(format="onnx", imgsz=args.imgsz, opset=13, simplify=True,
                                           dynamic=False, batch=1, verbose=False))
        dst = out_dir / "best.onnx"
        shutil.move(str(p), dst)
        report["onnx"] = {"file": "models/best.onnx", "size_mb": size_mb(dst), "opset": 13, "precision": "FP32",
                          "export_s": round(time.perf_counter() - t, 1)}
        print("onnx ->", dst, size_mb(dst), "MB")

    if args.format in ("tflite", "all"):
        t = time.perf_counter()
        kw = {"int8": True, "data": str(calibration_yaml(args.calib_n, args.seed))} if args.int8 else {}
        p = Path(YOLO(str(weights)).export(format="tflite", imgsz=args.imgsz, batch=1, verbose=False, **kw))
        saved = p.parent
        produced = {f.name: f for f in saved.glob("*.tflite")}
        for name, f in produced.items():
            if name.endswith("_full_integer_quant.tflite"):
                tag = "best_int8_full.tflite"
            elif name.endswith("_int8.tflite"):
                tag = "best_int8.tflite"
            elif name.endswith("_float16.tflite"):
                tag = "best_fp16.tflite"
            elif name.endswith("_float32.tflite"):
                tag = "best_fp32.tflite"
            else:
                continue
            shutil.copy2(f, out_dir / tag)
            report.setdefault("tflite", {})[tag] = {"file": f"models/{tag}", "size_mb": size_mb(out_dir / tag),
                                                    "from": name}
        if args.int8:
            report["tflite_calibration"] = json.loads((ROOT / "runs/calib/calib_info.json").read_text()) | {
                "split": "train (no augmented copies)", "seed": args.seed}
        report["tflite_export_s"] = round(time.perf_counter() - t, 1)
        print("tflite ->", {k: v["size_mb"] for k, v in report.get("tflite", {}).items()})

    ev_path.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
