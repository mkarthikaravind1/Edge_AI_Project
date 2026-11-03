"""M1.3: baseline speed of the whole pipeline (camera -> detect -> overlay).

Records FPS, per-frame latency (capture -> overlay done), inference latency, CPU %, GPU % (if any),
SoC temperature, and host info -> evidence/M1/baseline_<host>.json (+ per-frame csv).

    python scripts/benchmark_pipeline.py --seconds 60
"""

from __future__ import annotations

import argparse
import threading
import time

import psutil

from edgevision.config import load_config
from edgevision.detect import make_detector
from edgevision.evidence import write_csv, write_json
from edgevision.hal import make_camera
from edgevision.hostinfo import gpu_utilisation, host_tag, soc_temperature_c
from edgevision.pipeline import draw, summarise_ms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--source", default=None)
    ap.add_argument("--path", default=None)
    ap.add_argument("--tag", default=None, help="suffix for the output file, default = host")
    args = ap.parse_args()

    cfg = load_config()
    if args.source:
        cfg["camera"]["type"] = args.source
    if args.path:
        cfg["camera"]["path"] = args.path
    det = make_detector(cfg["detector"], cfg["classes"])
    cam = make_camera(cfg["camera"], realtime=False)

    for _ in range(args.warmup):
        fr = cam.read()
        if fr is not None:
            det.detect(fr.image)

    samples: list[dict] = []
    stop = threading.Event()

    def sampler() -> None:
        psutil.cpu_percent(None)
        while not stop.wait(1.0):
            samples.append({"t": round(time.perf_counter() - t0, 1), "cpu_pct": psutil.cpu_percent(None),
                            "gpu_pct": gpu_utilisation(), "temp_c": soc_temperature_c()})

    frames, e2e, infer = 0, [], []
    t0 = time.perf_counter()
    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    while time.perf_counter() - t0 < args.seconds:
        fr = cam.read()
        if fr is None:
            break
        ti = time.perf_counter()
        dets = det.detect(fr.image)
        infer.append(time.perf_counter() - ti)
        draw(fr.image, dets)
        e2e.append(time.perf_counter() - fr.t_capture)
        frames += 1
    elapsed = time.perf_counter() - t0
    stop.set()
    th.join()
    cam.close()

    def avg(k: str) -> float | None:
        v = [s[k] for s in samples if s[k] is not None]
        return round(sum(v) / len(v), 1) if v else None

    def peak(k: str) -> float | None:
        v = [s[k] for s in samples if s[k] is not None]
        return max(v) if v else None

    tag = args.tag or host_tag()
    res = {
        "camera": cfg["camera"]["type"], "backend": cfg["detector"]["backend"], "model": cfg["detector"]["model"],
        "imgsz": cfg["detector"]["imgsz"], "duration_s": round(elapsed, 2), "frames": frames,
        "fps": round(frames / elapsed, 2),
        "frame_latency": summarise_ms(e2e), "inference_latency": summarise_ms(infer),
        "cpu_pct_mean": avg("cpu_pct"), "cpu_pct_peak": peak("cpu_pct"),
        "gpu_pct_mean": avg("gpu_pct"), "temp_c_mean": avg("temp_c"), "temp_c_peak": peak("temp_c"),
        "note": "temperature/GPU are null when the host does not expose them (most Windows laptops)",
    }
    write_json("M1", f"baseline_{tag}", res)
    write_csv("M1", f"baseline_{tag}_samples", samples)
    print(f"FPS {res['fps']}  frame median {res['frame_latency'].get('median_ms')} ms  "
          f"p95 {res['frame_latency'].get('p95_ms')} ms  CPU {res['cpu_pct_mean']}%  temp {res['temp_c_mean']}")


if __name__ == "__main__":
    main()
