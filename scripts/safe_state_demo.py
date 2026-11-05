"""M3.4: break the camera -> the station drops into the SAFE STATE; plug it back -> it recovers.

Laptop: the video "cable" is pulled at --drop-at s and restored at --resume-at s (FlakyCamera).
Pi:     run with --live and physically unplug the USB webcam during the run, then plug it back in.

    python scripts/safe_state_demo.py                         -> evidence/M3/safe_state.json + .csv
    EDGE_TARGET=pi python scripts/safe_state_demo.py --live --seconds 40
"""

from __future__ import annotations

import argparse
import time

from edgevision.app import build_runtime
from edgevision.config import load_config
from edgevision.evidence import write_csv, write_json
from edgevision.hal import FlakyCamera


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use the configured camera; unplug it by hand")
    ap.add_argument("--seconds", type=float, default=12)
    ap.add_argument("--drop-at", type=float, default=4.0)
    ap.add_argument("--resume-at", type=float, default=8.0)
    args = ap.parse_args()

    cfg = load_config()
    if not args.live:
        cfg["camera"]["type"] = "video"
    rt = build_runtime(cfg, quiet_actuators=False)
    if not args.live:
        rt.camera = FlakyCamera(rt.camera, args.drop_at, args.resume_at)
        rt.camera_factory = None
    t0 = time.perf_counter()
    log = []
    rt.bus.subscribe("decision", lambda t, p: log.append({"t_s": round(p["t"] - t0, 3), **{k: v for k, v in p.items()
                                                                                           if k in ("event", "reason", "since_last_frame_s")}}))
    rt.run_for(args.seconds)

    hist = [{"t_s": round(t - t0, 3), "output": rt.run_permit.name, "change": e} for t, e in rt.run_permit.history]
    write_csv("M3", "safe_state_log", hist + [{"t_s": e["t_s"], "output": "event", "change": e["event"]} for e in log])
    safe = next((e for e in log if e["event"] == "safe_state"), None)
    rec = next((e for e in log if e["event"] == "recovered"), None)
    res = {"mode": "live unplug" if args.live else f"simulated unplug {args.drop_at}s -> {args.resume_at}s",
           "camera_timeout_s": cfg["decide"]["camera_timeout_s"],
           "safe_state_entered": safe is not None,
           "detect_time_after_last_frame_s": safe and safe.get("since_last_frame_s"),
           "safe_state_at_s": safe and safe["t_s"], "recovered_at_s": rec and rec["t_s"],
           "run_permit_history": hist, "events": log,
           "meaning": "run_permit OFF = conveyor stop. It goes off within camera_timeout_s (+ <=50 ms watchdog tick) of "
                      "the last frame and back on with the first good frame."}
    write_json("M3", "safe_state", res)
    print({k: res[k] for k in ("safe_state_entered", "detect_time_after_last_frame_s", "safe_state_at_s", "recovered_at_s")})


if __name__ == "__main__":
    main()
