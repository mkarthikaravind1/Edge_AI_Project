"""M4.8: drift report - are today's camera frames still like the frames the model was trained on?

Per frame: brightness (mean grey), contrast (std grey), sharpness (Laplacian variance), model confidence (best box),
boxes per frame. Baseline = real HELD-OUT frames (val + test: the model never trained on them, so its confidence on
them is honest). Each current sample is compared with PSI (population stability
index, 10 baseline-quantile bins) and the KS statistic.  PSI < 0.10 stable | 0.10-0.25 watch | > 0.25 DRIFT.

    python scripts/drift_report.py      # laptop: clip1 sharp frames | clip1 raw (hand-shake blur) | clip1 lamp failing
    EDGE_TARGET=pi python scripts/drift_report.py --live --seconds 30     # Pi: frames from the station camera
-> evidence/M4/drift_report.json + drift_report.png
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ks_2samp

from edgevision.config import load_config
from edgevision.detect import make_detector
from edgevision.evidence import evidence_dir, write_json
from edgevision.hal import make_camera

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["brightness", "contrast", "sharpness", "confidence", "boxes"]


def frame_stats(img: np.ndarray, det) -> list[float]:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dets = det.detect(img)
    return [float(g.mean()), float(g.std()), float(cv2.Laplacian(g, cv2.CV_64F).var()),
            max((d.conf for d in dets), default=0.0), float(len(dets))]


def psi(base: np.ndarray, cur: np.ndarray, bins: int = 5) -> float:
    edges = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    b = np.histogram(base, edges)[0] / len(base) + 1e-4
    c = np.histogram(cur, edges)[0] / len(cur) + 1e-4
    return float(np.sum((c - b) * np.log(c / b)))


def video_frames(path: Path, n: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for i in np.linspace(0, total - 1, n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            out.append(f)
    return out


def lamp_failing(img: np.ndarray) -> np.ndarray:
    dark = cv2.convertScaleAbs(img, alpha=0.45, beta=-10)
    return cv2.GaussianBlur(dark, (0, 0), 2.0)


def compare(base: dict[str, np.ndarray], cur: np.ndarray, bins: int = 5) -> dict:
    """noise_floor = PSI expected from sampling alone, (bins-1)*(1/n_base + 1/n_cur): a small baseline makes PSI
    jumpy, so DRIFT needs PSI > 0.25 AND > 3x that floor; 'watch' needs > 0.10 AND > 2x the floor."""
    out = {}
    for k, name in enumerate(FEATURES):
        b, c = base[name], cur[:, k]
        p = psi(b, c, bins)
        floor = (bins - 1) * (1 / len(b) + 1 / len(c))
        status = "DRIFT" if p > max(0.25, 3 * floor) else ("watch" if p > max(0.10, 2 * floor) else "stable")
        out[name] = {"baseline_n": len(b), "baseline_median": round(float(np.median(b)), 2),
                     "current_median": round(float(np.median(c)), 2), "psi": round(p, 3),
                     "noise_floor": round(floor, 3), "ks": round(float(ks_2samp(b, c).statistic), 3), "status": status}
    order = {"stable": 0, "watch": 1, "DRIFT": 2}
    out["_overall"] = max((v["status"] for v in out.values()), key=order.get)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--video", default="data/raw/videos/clip1.mp4")
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()

    cfg = load_config()
    det = make_detector(cfg["detector"], cfg["classes"])
    # confidence / boxes: held-out frames only (the model is over-confident on frames it trained on)
    held = sorted((ROOT / "data/splits/test/images").glob("*.jpg")) +         sorted((ROOT / "data/splits/val/images").glob("clip*.jpg"))          # val images exist on the laptop only
    held_stats = np.array([frame_stats(cv2.imread(str(p)), det) for p in held])
    # brightness / contrast / sharpness do not depend on the model: use every extracted real frame (bigger = steadier)
    allf = sorted((ROOT / "data/frames/images").glob("*.jpg")) or held
    img_stats = np.array([frame_stats(cv2.imread(str(p)), det)[:3] for p in allf])
    base = {"brightness": img_stats[:, 0], "contrast": img_stats[:, 1], "sharpness": img_stats[:, 2],
            "confidence": held_stats[:, 3], "boxes": held_stats[:, 4]}

    samples: dict[str, list[np.ndarray]] = {}
    if args.live:
        cam = make_camera(cfg["camera"], realtime=True)
        frames, t0 = [], time.perf_counter()
        while time.perf_counter() - t0 < args.seconds:
            fr = cam.read()
            if fr is not None and len(frames) < 10_000:
                frames.append(fr.image)
            time.sleep(args.seconds / args.n)
        cam.close()
        samples["live_camera"] = frames
    else:
        frames = video_frames(ROOT / args.video, args.n)
        sharp = [f for f in frames if cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var() >= 60]
        samples["clip1_sharp (same blur gate as the dataset)"] = sharp
        samples["clip1_raw (incl. hand-shake blur)"] = frames
        samples["clip1_lamp_failing (simulated: 45% light + blur)"] = [lamp_failing(f) for f in sharp]

    res = {"baseline": {"image_stats": f"{len(img_stats)} real dataset frames", "confidence": f"{len(held_stats)} held-out real frames (test + val)"},
           "psi_rule": "5 baseline-quantile bins; DRIFT: PSI > 0.25 and > 3x noise floor; watch: > 0.10 and > 2x floor",
           "samples": {}}
    stats = {}
    for name, imgs in samples.items():
        cur = np.array([frame_stats(i, det) for i in imgs])
        stats[name] = cur
        res["samples"][name] = {"frames": len(cur), **compare(base, cur)}
        print(name, "->", res["samples"][name]["_overall"],
              {k: res["samples"][name][k]["psi"] for k in FEATURES})

    fig, axs = plt.subplots(1, len(FEATURES), figsize=(17, 3.4))
    for k, (ax, name) in enumerate(zip(axs, FEATURES)):
        bins = np.histogram_bin_edges(np.concatenate([base[name], *[s[:, k] for s in stats.values()]]), 25)
        ax.hist(base[name], bins, alpha=0.5, density=True, label="baseline", color="grey")
        for s_name, s in stats.items():
            ax.hist(s[:, k], bins, histtype="step", lw=1.6, density=True, label=s_name.split(" (")[0])
        ax.set_title(name)
    axs[0].legend(fontsize=7)
    fig.suptitle("Input / confidence drift vs baseline (grey)", y=1.02)
    fig.tight_layout()
    fig.savefig(evidence_dir("M4") / "drift_report.png", dpi=110, bbox_inches="tight")
    write_json("M4", "drift_report", res)


if __name__ == "__main__":
    main()
