"""M4.2 + M4.3: train the motor anomaly model on NORMAL data only, choose the threshold, count false alarms.

Runs used (default):
  train      normal_1, normal_2           features of 1 s windows, every 0.5 s
  calibrate  normal_3                     threshold = 99.5th percentile of its scores (held out from training)
  evaluate   normal_4 .. normal_8         5 unseen normal runs -> false alarms
             fault_*                      every fault run must raise an alert
Alert = 2 windows in a row above the threshold (one noisy window cannot alarm).

    python scripts/train_anomaly.py --data data/imu/synthetic        # development (SYNTHETIC, clearly labelled)
    python scripts/train_anomaly.py --data data/imu/real             # real MPU6050 runs from the Pi
-> models/anomaly.json, evidence/M4/anomaly_model.json, evidence/M4/false_alarms.json, evidence/M4/anomaly_scores.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from edgevision.config import load_config, resolve
from edgevision.monitor import AnomalyModel, feature_names, sliding_windows, window_features
from edgevision.monitor.live import score_run

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> np.ndarray:
    return np.loadtxt(path, delimiter=",", skiprows=1)[:, 1:7]


def feats(data: np.ndarray, rate: float, win: float, step: float) -> np.ndarray:
    return np.array([window_features(w, rate) for w in sliding_windows(data, int(win * rate), int(step * rate))])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/imu/synthetic")
    ap.add_argument("--train", nargs="+", default=["normal_1", "normal_2"])
    ap.add_argument("--calib", default="normal_3")
    ap.add_argument("--eval-normal", nargs="+", default=[f"normal_{i}" for i in range(4, 9)])
    ap.add_argument("--percentile", type=float, default=None)
    ap.add_argument("--alert-n", type=int, default=2)
    args = ap.parse_args()

    cfg = load_config()
    a = cfg["anomaly"]
    rate, win, step = cfg["imu"].get("rate_hz", 200), a["window_s"], a["step_s"]
    pct = args.percentile or a["threshold_percentile"]
    d = ROOT / args.data
    synthetic = "synthetic" in d.as_posix()

    train = np.vstack([feats(load(d / f"{n}.csv"), rate, win, step) for n in args.train])
    calib = feats(load(d / f"{args.calib}.csv"), rate, win, step)
    model = AnomalyModel.fit(train, calib_feats=calib, percentile=pct)
    model.save(resolve(a["model_path"]))

    runs = {}
    for name in args.eval_normal + sorted(p.stem for p in d.glob("fault_*.csv")):
        if not (d / f"{name}.csv").exists():
            print(f"skip {name}: not recorded")
            continue
        runs[name] = score_run(model, load(d / f"{name}.csv"), rate, win, step, args.alert_n)

    normal = {k: v for k, v in runs.items() if k.startswith("normal")}
    fault = {k: v for k, v in runs.items() if k.startswith("fault")}
    fa = sum(v["alerts"] for v in normal.values())
    minutes = sum(v["windows"] for v in normal.values()) * step / 60
    detected = sum(v["alerts"] > 0 for v in fault.values())
    data_note = "SYNTHETIC data (scripts/gen_synthetic_imu.py) - development only, replace with real MPU6050 runs" \
        if synthetic else "real MPU6050 runs recorded with scripts/record_imu.py"

    ev = ROOT / "evidence/M4"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "anomaly_model.json").write_text(json.dumps({
        "data": data_note, "model": "per-feature z-score (diagonal Mahalanobis) on log features, trained on normal only",
        "features": f"{len(feature_names())} = 6 axes x (RMS, peak, FFT band energy 0-5/5-20/20-50/50-100 Hz)",
        "window_s": win, "step_s": step, "rate_hz": rate, "train_runs": args.train, "train_windows": len(train),
        "calibration_run": args.calib, "threshold_percentile": pct, "threshold": round(model.threshold, 3),
        "alert_rule": f"{args.alert_n} windows in a row above threshold",
        "fault_runs_detected": f"{detected}/{len(fault)}",
        "fault_runs": {k: {kk: vv for kk, vv in v.items() if kk != "scores"} for k, v in fault.items()}}, indent=2))
    (ev / "false_alarms.json").write_text(json.dumps({
        "data": data_note, "normal_runs_evaluated": list(normal), "unseen_by_training_and_threshold": True,
        "false_alarms_total": fa, "normal_minutes": round(minutes, 2),
        "false_alarms_per_hour": round(fa / minutes * 60, 2) if minutes else None,
        "per_run": {k: {kk: vv for kk, vv in v.items() if kk != "scores"} for k, v in normal.items()},
        "threshold": round(model.threshold, 3), "threshold_percentile": pct, "target": "<= 1 false alarm over 5 normal runs",
        "met": fa <= 1,
        "threshold_choice": (f"{pct}th percentile of scores on a normal run NOT used for training: about 1 window in "
                             f"{int(100 / (100 - pct))} of normal data is above it, and the 2-in-a-row rule turns that "
                             "into very few alarms. A training-run percentile would be too low because the model "
                             "always fits its own training windows best.")}, indent=2))

    fig, ax = plt.subplots(figsize=(11, 4.5))
    for k, v in runs.items():
        x = np.arange(len(v["scores"])) * step + win
        ax.plot(x, v["scores"], lw=1.2 if k.startswith("fault") else 0.8,
                color=None if k.startswith("fault") else "grey", alpha=1 if k.startswith("fault") else 0.6,
                label=k if k.startswith("fault") or k == args.eval_normal[0] else None)
    ax.axhline(model.threshold, color="red", ls="--", label=f"threshold ({pct}th pct of {args.calib})")
    ax.set_yscale("log")
    ax.set_xlabel("time in run (s)")
    ax.set_ylabel("anomaly score (log)")
    ax.set_title(("SYNTHETIC - " if synthetic else "") + f"motor anomaly score: grey = 5 unseen normal runs, colour = fault runs")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(ev / "anomaly_scores.png", dpi=110)
    print(f"threshold {model.threshold:.2f} | false alarms {fa} over {len(normal)} normal runs ({minutes:.1f} min) "
          f"| faults detected {detected}/{len(fault)} | {data_note}")


if __name__ == "__main__":
    main()
