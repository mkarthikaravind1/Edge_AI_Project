"""M4.2: live motor monitor with an injected fault -> ALERT, and time-to-alert.

Laptop: replays a normal run, then switches to a fault run at --inject-at s (simulated injection, real-time 200 Hz).
Pi:     --live reads the MPU6050; press ENTER the moment you inject the fault (tap the mount / add the unbalance).

    python scripts/motor_monitor.py                           -> evidence/M4/live_alert.json
    EDGE_TARGET=pi python scripts/motor_monitor.py --live --seconds 40
"""

from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import numpy as np

from edgevision.bus import EventBus
from edgevision.config import load_config, resolve
from edgevision.evidence import write_json
from edgevision.hal import make_imu
from edgevision.hal.imu import Imu, ImuSample
from edgevision.monitor import AnomalyModel, MotorMonitor

ROOT = Path(__file__).resolve().parents[1]


class SpliceImu(Imu):
    """Normal run until inject_at seconds of samples, then the fault run."""

    def __init__(self, normal: Path, fault: Path, rate: float, inject_at: float) -> None:
        a = np.loadtxt(normal, delimiter=",", skiprows=1)
        b = np.loadtxt(fault, delimiter=",", skiprows=1)
        k = int(inject_at * rate)
        self.rows = np.vstack([a[:k], b[: len(a) - k]])
        self.i = 0

    def read(self) -> ImuSample | None:
        if self.i >= len(self.rows):
            return None
        r = self.rows[self.i]
        self.i += 1
        return ImuSample(*map(float, r))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--data", default="data/imu/synthetic")
    ap.add_argument("--normal", default="normal_5")
    ap.add_argument("--fault", default="fault_unbalance_1")
    ap.add_argument("--inject-at", type=float, default=10.0)
    ap.add_argument("--seconds", type=float, default=20.0)
    args = ap.parse_args()

    cfg = load_config()
    model = AnomalyModel.load(resolve(cfg["anomaly"]["model_path"]))
    rate = cfg["imu"].get("rate_hz", 200)
    if args.live:
        imu = make_imu(cfg["imu"])
    else:
        d = ROOT / args.data
        imu = SpliceImu(d / f"{args.normal}.csv", d / f"{args.fault}.csv", rate, args.inject_at)
    bus = EventBus()
    events = []
    t0 = time.perf_counter()
    inject_t = [None if args.live else args.inject_at]
    bus.subscribe("motor", lambda t, p: events.append({"t_s": round(time.perf_counter() - t0, 2), "score": p["score"],
                                                       "alert": p["alert"], "change": p["change"]}))
    bus.subscribe("motor", lambda t, p: p["change"] and print(f"{time.perf_counter() - t0:6.2f}s  MOTOR {p['change'].upper()}  "
                                                             f"score {p['score']} (threshold {p['threshold']})"))
    mon = MotorMonitor(imu, model, cfg, bus, cfg.get("device_id", "edge"))
    mon.start()
    if args.live:
        def wait_enter() -> None:
            input("press ENTER at the moment you inject the fault...\n")
            inject_t[0] = round(time.perf_counter() - t0, 2)
            print(f"fault injected at {inject_t[0]} s")
        threading.Thread(target=wait_enter, daemon=True).start()
    time.sleep(args.seconds)
    mon.stop()

    first_alert = next((e["t_s"] for e in events if e["change"] == "alert"), None)
    before = [e for e in events if inject_t[0] is not None and e["t_s"] < inject_t[0]]
    res = {"source": "MPU6050 live" if args.live else f"SYNTHETIC replay: {args.normal} then {args.fault} at {args.inject_at}s (200 Hz real time)",
           "threshold": round(model.threshold, 3), "alert_rule": f"{cfg['anomaly'].get('alert_n', 2)} windows in a row",
           "fault_injected_at_s": inject_t[0], "first_alert_at_s": first_alert,
           "time_to_alert_s": round(first_alert - inject_t[0], 2) if first_alert and inject_t[0] is not None else None,
           "alerts_before_injection": sum(e["change"] == "alert" for e in before),
           "windows": len(events), "timeline": events}
    write_json("M4", "live_alert", res)
    print({k: res[k] for k in ("fault_injected_at_s", "first_alert_at_s", "time_to_alert_s", "alerts_before_injection")})


if __name__ == "__main__":
    main()
