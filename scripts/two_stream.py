"""M3.2: two camera streams at once, one thread each; FPS per stream.

Two set-ups are measured:
  shared   - ONE model instance used by both threads behind a lock (least memory; a TFLite interpreter is
             not thread-safe, so the lock is required)
  separate - one model instance per stream (more memory, both can infer at the same time)

    python scripts/two_stream.py --seconds 20                         # laptop: video + video
    EDGE_TARGET=pi python scripts/two_stream.py --seconds 30          # Pi: USB webcam + recorded frames (config camera/camera2)
-> evidence/M3/two_stream_<host>.json
"""

from __future__ import annotations

import argparse

from edgevision.config import load_config
from edgevision.detect import make_detector
from edgevision.evidence import write_json
from edgevision.hal import make_camera
from edgevision.hostinfo import host_tag
from edgevision.pipeline import run_two_streams, summarise_ms


def measure(cfg: dict, shared: bool, seconds: float, realtime: bool) -> dict:
    cams = {"stream1": make_camera(cfg["camera"], realtime=realtime),
            "stream2": make_camera(cfg["camera2"], realtime=realtime)}
    if shared:
        d = make_detector(cfg["detector"], cfg["classes"])
        dets = {"stream1": d, "stream2": d}
    else:
        dets = {k: make_detector(cfg["detector"], cfg["classes"]) for k in cams}
    for k, d in dets.items():       # warm-up outside the timing
        fr = cams[k].read()
        if fr is not None:
            d.detect(fr.image)
    res = run_two_streams(cams, dets, seconds, shared_lock=shared)
    for c in cams.values():
        c.close()
    out = {k: {"frames": s.frames, "fps": round(s.fps, 2), "errors": s.errors, "infer": summarise_ms(s.infer_s)}
           for k, s in res.items()}
    out["total_fps"] = round(sum(s.fps for s in res.values()), 2)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20)
    args = ap.parse_args()
    cfg = load_config()
    if cfg.get("target") == "laptop":
        cfg["camera"]["type"] = cfg["camera2"]["type"] = "video"
    res = {"camera1": cfg["camera"]["type"], "camera2": cfg["camera2"]["type"],
           "backend": cfg["detector"]["backend"], "model": cfg["detector"]["model"], "seconds": args.seconds}
    for name, shared, realtime in (("shared_model_realtime", True, True), ("separate_models_realtime", False, True),
                                   ("shared_model_max", True, False), ("separate_models_max", False, False)):
        if cfg.get("target") != "laptop" and not realtime:
            continue                 # real cameras are always real-time
        r = measure(cfg, shared, args.seconds, realtime)
        res[name] = r
        print(name, {k: v["fps"] for k, v in r.items() if isinstance(v, dict)}, "total", r["total_fps"])
    res["note"] = ("realtime = each source delivers at most its native 30 FPS, like a real camera; "
                   "max = frames as fast as the model allows (shows spare capacity)")
    write_json("M3", f"two_stream_{host_tag()}", res)


if __name__ == "__main__":
    main()
