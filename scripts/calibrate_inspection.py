"""M5.2: learn the inspection limits from GOOD parts only (no defect examples needed).

For every good image: detect the enclosure, measure mark_frac / rect_fill / vertices. Limits:
  mark_frac_max = 1.5 x the largest dark area seen on any good part (+ 0.002 floor)
  rect_fill_min = the least rectangular good part - 0.03
  solidity_min  = the least solid good part - 0.02          (a bite out of a corner makes the outline concave)
So every good calibration part passes by construction; the test set (different parts) shows how well it generalises.

    python scripts/calibrate_inspection.py --dir data/rig_sim/calib_good      # laptop stand-in
    python scripts/calibrate_inspection.py --dir data/rig/calib_good          # real rig images (Pi)
-> models/inspection.json + evidence/M5/inspection_calibration.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from edgevision.config import load_config, resolve
from edgevision.detect import make_detector
from edgevision.evidence import write_json
from edgevision.inspect import part_features

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/rig_sim/calib_good")
    args = ap.parse_args()
    cfg = load_config()
    det = make_detector(cfg["detector"], cfg["classes"])
    thr = cfg["decide"]["conf_threshold"]
    rows = []
    for p in sorted((ROOT / args.dir).glob("*.jpg")):
        img = cv2.imread(str(p))
        enc = [d for d in det.detect(img) if d.name == "enclosure" and d.conf >= thr]
        f = part_features(img, max(enc, key=lambda d: d.conf).box) if enc else None
        rows.append({"file": p.name, "enclosure_found": bool(enc), **(f or {})})
    ok = [r for r in rows if "mark_frac" in r]
    if not ok:
        raise SystemExit("no usable good images")
    mf = np.array([r["mark_frac"] for r in ok])
    rf = np.array([r["rect_fill"] for r in ok])
    so = np.array([r["solidity"] for r in ok])
    limits = {"mark_frac_max": round(float(max(mf.max() * 1.5, mf.max() + 0.002)), 5),
              "rect_fill_min": round(float(rf.min() - 0.03), 4),
              "solidity_min": round(float(so.min() - 0.02), 4)}
    out = resolve(cfg.get("inspection", {}).get("model_path", "models/inspection.json"))
    out.write_text(json.dumps({"limits": limits, "calibrated_on": args.dir, "good_images": len(ok)}, indent=2))
    write_json("M5", "inspection_calibration", {
        "dir": args.dir, "images": len(rows), "usable": len(ok), "limits": limits,
        "good_feature_ranges": {"mark_frac": [round(float(mf.min()), 5), round(float(mf.max()), 5)],
                                "rect_fill": [round(float(rf.min()), 4), round(float(rf.max()), 4)],
                                "solidity": [round(float(so.min()), 4), round(float(so.max()), 4)]},
        "rule": "limits from good parts only: mark 1.5x worst good (+0.002), rectangularity worst good - 0.03, solidity worst good - 0.02",
        "slot_rule": "dark blobs that are long thin boxes (aspect >= 3.5, box fill >= 0.55) are the designed slot, not marks",
        "per_image": rows})
    print("limits", limits, "from", len(ok), "good images")


if __name__ == "__main__":
    main()
