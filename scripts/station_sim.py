"""Run the COMPLETE station on the laptop with a simulated conveyor: camera -> detect -> inspect -> decide -> act
-> MQTT -> dashboard, plus the motor monitor. Used for the dashboard demo and the M5.3 full-chain endurance run.

Parts = the rig images (good + defective) shown one at a time for --part-s, then --gap-s of empty background,
at 30 FPS. Motor = synthetic normal vibration, with an injected fault between --fault-at and --fault-until.

    python scripts/station_sim.py --minutes 2                    # dashboard on http://localhost:8000
    python scripts/station_sim.py --minutes 10 --mqtt --report   # M5.3: 10-minute chain -> evidence/M5/full_chain_laptop.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from edgevision.app import attach_plugins, build_runtime   # noqa: E402
from edgevision.config import load_config                  # noqa: E402
from edgevision.dashboard.server import serve_in_thread    # noqa: E402
from edgevision.evidence import write_json                 # noqa: E402
from edgevision.hal.camera import Camera                   # noqa: E402
from edgevision.hal.imu import Imu, ImuSample              # noqa: E402
from edgevision.ops.logs import setup_logging              # noqa: E402
from edgevision.pipeline import summarise_ms               # noqa: E402


class PartFeeder(Camera):
    """Each part image for part_s, then background for gap_s; records which truth was shown for each part."""

    def __init__(self, items: list[tuple[np.ndarray, str]], fps: float, part_s: float, gap_s: float) -> None:
        super().__init__()
        self.items, self.period = items, 1.0 / fps
        self.n_part, self.n_gap = int(part_s * fps), int(gap_s * fps)
        self.shown: list[str] = []
        # empty belt = the same scene blurred beyond recognition; computed ONCE per part (a sigma-60 blur costs ~0.6 s)
        self.empty = [cv2.GaussianBlur(img, (0, 0), 60) for img, _ in items]
        self._k = 0
        self._next = time.perf_counter()

    def _grab(self) -> np.ndarray:
        delay = self._next - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        self._next = max(self._next + self.period, time.perf_counter())
        cyc = self.n_part + self.n_gap
        idx, k = divmod(self._k, cyc)
        self._k += 1
        img, truth = self.items[idx % len(self.items)]
        if k == 0:
            self.shown.append(truth)
        if k < self.n_part:
            return img
        return self.empty[idx % len(self.items)]


class FaultImu(Imu):
    """Loops a normal run; between fault_at and fault_until (s) it plays a fault run instead."""

    def __init__(self, normal: Path, fault: Path, fault_at: float, fault_until: float) -> None:
        self.a = np.loadtxt(normal, delimiter=",", skiprows=1)
        self.b = np.loadtxt(fault, delimiter=",", skiprows=1)
        self.fault_at, self.fault_until, self.i, self.t0 = fault_at, fault_until, 0, time.perf_counter()

    def read(self) -> ImuSample:
        t = time.perf_counter() - self.t0
        src = self.b if self.fault_at <= t < self.fault_until else self.a
        r = src[self.i % len(src)]
        self.i += 1
        return ImuSample(*map(float, r))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=2)
    ap.add_argument("--dir", default="data/rig_sim/test")
    ap.add_argument("--part-s", type=float, default=2.0)
    ap.add_argument("--gap-s", type=float, default=1.5)
    ap.add_argument("--fault-at", type=float, default=40)
    ap.add_argument("--fault-until", type=float, default=55)
    ap.add_argument("--mqtt", action="store_true")
    ap.add_argument("--auto-truth", action="store_true", help="mark each part's truth automatically (headline demo)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    cfg["inspection"]["enabled"] = True
    cfg["mqtt"]["enabled"] = args.mqtt
    cfg["camera"]["type"] = "video"
    setup_logging(cfg, "station_sim")
    rt = build_runtime(cfg, quiet_actuators=True)
    d = ROOT / args.dir
    items = [(cv2.imread(str(p)), t) for t in ("good", "defective") for p in sorted((d / t).glob("*.jpg"))]
    random.Random(0).shuffle(items)
    feeder = PartFeeder(items, 30, args.part_s, args.gap_s)
    rt.camera, rt.camera_factory = feeder, None

    from edgevision.monitor import AnomalyModel, MotorMonitor
    from edgevision.config import resolve
    syn = ROOT / "data/imu/synthetic"
    mon = MotorMonitor(FaultImu(syn / "normal_6.csv", syn / "fault_unbalance_2.csv", args.fault_at, args.fault_until),
                       AnomalyModel.load(resolve(cfg["anomaly"]["model_path"])), cfg, rt.bus, rt.device_id)
    rt.motor = mon
    plugins = [p for p in attach_plugins(rt, {**cfg, "imu": None}) if p is not mon]
    if args.auto_truth:                                   # the truth of the k-th part shown is feeder.shown[k-1]
        rt.bus.subscribe("part", lambda t, p: [setattr(x, "truth", feeder.shown[x.id - 1]) for x in rt.parts if x.id == p["id"]])
    server = serve_in_thread(rt, cfg)
    errors_seen = []
    rt.bus.subscribe("decision", lambda t, p: p.get("event") == "safe_state" and errors_seen.append(p))
    print(f"station running for {args.minutes} min - dashboard http://localhost:{cfg['dashboard']['port']}", flush=True)
    t0 = time.perf_counter()
    rt.start()
    mon.start()
    samples = []
    while time.perf_counter() - t0 < args.minutes * 60:
        time.sleep(5)
        s = rt.stats()
        samples.append({"t_s": round(time.perf_counter() - t0), "fps": s["fps"], "frames": s["frames"],
                        "parts": s["parts"], "errors": sum(s["errors"].values()), "state": s["state"]})
    mon.stop()
    rt.stop()
    for p in plugins:
        p.close()
    server.should_exit = True

    if args.report:
        from edgevision.dashboard.kpis import kpis
        parts = [p.to_dict() for p in rt.parts]
        for p in parts:                                   # ground truth from the feeder for the evidence file
            p["truth"] = feeder.shown[p["id"] - 1] if p["id"] - 1 < len(feeder.shown) else None
        judged = [p for p in parts if p["result"] in ("PASS", "FAIL") and p["truth"]]
        correct = sum((p["result"] == "PASS") == (p["truth"] == "good") for p in judged)
        bad = [p for p in judged if p["truth"] == "defective"]
        fps = [x["fps"] for x in samples[1:]]
        res = {"duration_min": args.minutes, "uptime_s": round(time.perf_counter() - t0, 1),
               "chain": "camera(sim conveyor) -> TFLite INT8 -> inspection -> decision -> reject/PLC/run_permit -> "
                        + ("MQTT TLS -> " if args.mqtt else "") + "dashboard (+ motor monitor)",
               "frames": rt.frames, "fps_mean": round(float(np.mean(fps)), 2) if fps else None,
               "fps_min": round(float(np.min(fps)), 2) if fps else None,
               "errors": dict(rt.errors), "safe_state_events": len(errors_seen),
               "parts_shown": len(feeder.shown), "parts_tracked": len(parts),
               "parts_correct": f"{correct}/{len(judged)}",
               "false_pass_rate": round(sum(p["result"] == "PASS" for p in bad) / len(bad), 3) if bad else None,
               "reject_latency": summarise_ms([l["first_hit_to_cmd_ms"] / 1000 for l in rt.latencies]),
               "motor_alerts": mon.alerts, "mqtt_messages_sent": sum(getattr(p, "sent", 0) for p in plugins),
               "kpis_at_end": kpis(rt), "fps_timeline": samples,
               "what_broke_and_fix": []}
        write_json("M5", "full_chain_laptop", res)
        print(json.dumps({k: res[k] for k in ("uptime_s", "fps_mean", "fps_min", "errors", "parts_shown",
                                              "parts_tracked", "parts_correct", "false_pass_rate", "motor_alerts",
                                              "mqtt_messages_sent")}, indent=1))


if __name__ == "__main__":
    main()
