"""M4.1: record one labelled IMU run to CSV (t, ax, ay, az [g], gx, gy, gz [deg/s]).

Pi (MPU6050 on I2C-1), motor running:
    EDGE_TARGET=pi python scripts/record_imu.py --label normal --run 1 --seconds 30
    EDGE_TARGET=pi python scripts/record_imu.py --label fault_unbalance --run 1 --seconds 30   # tape a coin to the rotor
    EDGE_TARGET=pi python scripts/record_imu.py --label fault_tap --run 1 --seconds 30         # tap the mount every ~1 s
-> data/imu/real/<label>_<run>.csv  (+ the achieved sample rate in data/imu/real/runs.json)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from edgevision.config import load_config
from edgevision.hal import make_imu
from edgevision.hal.imu import COLUMNS

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="normal | fault_unbalance | fault_tap | ...")
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--out", default="data/imu/real")
    args = ap.parse_args()

    cfg = load_config()
    imu = make_imu(cfg["imu"])
    rate = cfg["imu"].get("rate_hz", 200)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{args.label}_{args.run}.csv"
    print(f"recording {args.label} run {args.run} for {args.seconds}s at {rate} Hz -> {path}")
    t0 = time.perf_counter()
    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for s in imu.stream(rate, args.seconds):
            row = s.as_row()
            row[0] = time.perf_counter() - t0
            w.writerow([f"{v:.5f}" for v in row])
            n += 1
    dt = time.perf_counter() - t0
    imu.close()
    meta_path = out / "runs.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta[path.name] = {"label": args.label, "run": args.run, "samples": n, "seconds": round(dt, 2),
                       "achieved_hz": round(n / dt, 1), "source": cfg["imu"]["type"]}
    meta_path.write_text(json.dumps(meta, indent=2))
    print(meta[path.name])


if __name__ == "__main__":
    main()
