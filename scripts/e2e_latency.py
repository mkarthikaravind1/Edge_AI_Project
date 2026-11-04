"""M3.6: end-to-end latency, frame capture -> actuator command, over >= 20 trigger events.

Two numbers per event:
  frame_to_cmd_ms      capture timestamp of the frame that fired -> reject output written  (pipeline cost)
  first_hit_to_cmd_ms  capture of the FIRST hit frame of that part -> output written       (+ the N-of-M wait)

Laptop: a simulated conveyor (real test images of a part for --part-s, empty background for --gap-s, at 30 FPS).
Pi:     --live uses the real camera; pass parts under it by hand (one every ~3 s) until 20+ events are logged.

    python scripts/e2e_latency.py --events 25
    EDGE_TARGET=pi python scripts/e2e_latency.py --live --events 25
-> evidence/M3/e2e_latency_<host>.json + .csv
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from edgevision.app import build_runtime
from edgevision.config import load_config
from edgevision.evidence import write_csv, write_json
from edgevision.hal.camera import Camera
from edgevision.hostinfo import host_tag
from edgevision.pipeline import summarise_ms

ROOT = Path(__file__).resolve().parents[1]


class ConveyorSim(Camera):
    """Delivers frames at a fixed FPS: part images for part_s, then plain background for gap_s, repeated."""

    def __init__(self, parts: list[np.ndarray], fps: float, part_s: float, gap_s: float) -> None:
        super().__init__()
        self.parts, self.period = parts, 1.0 / fps
        self.cycle = [("part", int(part_s * fps)), ("gap", int(gap_s * fps))]
        self.empty = cv2.GaussianBlur(parts[0], (0, 0), 60)
        self._seq = 0
        self._next = time.perf_counter()

    def _grab(self) -> np.ndarray | None:
        delay = self._next - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        self._next = max(self._next + self.period, time.perf_counter())
        n_part, n_gap = self.cycle[0][1], self.cycle[1][1]
        k = self._seq % (n_part + n_gap)
        part_idx = (self._seq // (n_part + n_gap)) % len(self.parts)
        self._seq += 1
        return self.parts[part_idx] if k < n_part else self.empty


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--events", type=int, default=25)
    ap.add_argument("--part-s", type=float, default=1.5)
    ap.add_argument("--gap-s", type=float, default=1.5)
    ap.add_argument("--max-seconds", type=float, default=300)
    args = ap.parse_args()

    cfg = load_config()
    if not args.live:
        cfg["camera"]["type"] = "video"       # placeholder; replaced by the simulator below
    rt = build_runtime(cfg, quiet_actuators=True)
    if not args.live:
        imgs = [cv2.imread(str(p)) for p in sorted((ROOT / "data/splits/test/images").glob("*.jpg"))]
        dets = [rt.detector.detect(i) for i in imgs]
        parts = [i for i, d in zip(imgs, dets) if rt.engine.is_hit(d)]
        rt.camera = ConveyorSim(parts, fps=30, part_s=args.part_s, gap_s=args.gap_s)
        rt.camera_factory = None
    rt.start()
    t0 = time.perf_counter()
    while len(rt.latencies) < args.events and time.perf_counter() - t0 < args.max_seconds:
        time.sleep(0.2)
    rt.stop()

    lat = rt.latencies[: max(args.events, len(rt.latencies))]
    rows = [{"event": i + 1, **l} for i, l in enumerate(lat)]
    write_csv("M3", f"e2e_latency_{host_tag()}", rows)
    res = {"source": "live camera" if args.live else f"simulated conveyor ({args.part_s}s part / {args.gap_s}s gap, 30 FPS, real test images)",
           "backend": cfg["detector"]["backend"], "model": cfg["detector"]["model"],
           "rule": f"{cfg['decide']['n']}-of-{cfg['decide']['m']}, conf >= {cfg['decide']['conf_threshold']}",
           "events": len(lat), "frames": rt.frames, "fps": round(rt.frames / (time.perf_counter() - t0), 2),
           "frame_to_cmd": summarise_ms([l["frame_to_cmd_ms"] / 1000 for l in lat]),
           "first_hit_to_cmd": summarise_ms([l["first_hit_to_cmd_ms"] / 1000 for l in lat]),
           "target_p95_ms": 600}
    write_json("M3", f"e2e_latency_{host_tag()}", res)
    print(f"events {res['events']}  frame->cmd median {res['frame_to_cmd'].get('median_ms')} ms p95 {res['frame_to_cmd'].get('p95_ms')} ms"
          f" | first hit->cmd median {res['first_hit_to_cmd'].get('median_ms')} ms p95 {res['first_hit_to_cmd'].get('p95_ms')} ms")


if __name__ == "__main__":
    main()
