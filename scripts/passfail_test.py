"""M5.2: the 20-part pass/fail test -> confusion matrix and FALSE-PASS rate.

Images: <dir>/good/*.jpg and <dir>/defective/*.jpg (10 + 10). Each image = one part; it is run through the same
detector + inspector as the live station. A false pass = a defective part judged PASS (the costly error).

    python scripts/passfail_test.py --dir data/rig_sim/test             # laptop stand-in (see manifest: real + simulated)
    python scripts/passfail_test.py --dir data/rig/test                 # real 20 parts shot on the rig
-> evidence/M5/passfail.json + passfail_confusion.png + passfail_results.csv + passfail_sheet.jpg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from edgevision.config import load_config
from edgevision.detect import make_detector
from edgevision.evidence import evidence_dir, write_csv, write_json
from edgevision.inspect import make_inspector
from edgevision.pipeline import draw

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/rig_sim/test")
    args = ap.parse_args()
    cfg = load_config()
    det = make_detector(cfg["detector"], cfg["classes"])
    insp = make_inspector(cfg)
    d = ROOT / args.dir
    manifest = {}
    mp = d.parent / "manifest.json"
    if mp.exists():
        manifest = {Path(m["file"]).name: m for m in json.loads(mp.read_text())}

    rows, tiles = [], []
    for truth in ("good", "defective"):
        for p in sorted((d / truth).glob("*.jpg")):
            img = cv2.imread(str(p))
            dets = det.detect(img)
            v = insp(img, dets)
            pred = "PASS" if v["verdict"] == "PASS" else "FAIL"     # NONE (nothing found) counts as FAIL: never pass blind
            m = manifest.get(p.name, {})
            defect = m.get("defect") or (p.stem.split("_")[0] if truth == "defective" else "")   # capture_rig.py prefix
            rows.append({"file": p.name, "truth": truth, "defect": defect, "source": m.get("source", "real"),
                         "verdict": v["verdict"], "pred": pred, "reasons": "+".join(v["reasons"]),
                         "correct": (pred == "PASS") == (truth == "good"), **v.get("features", {})})
            vis = draw(img, [x for x in dets if x.conf >= 0.25], None,
                       [f"{v['verdict']} {'+'.join(v['reasons'])}"[:24], f"truth: {truth}"])
            colour = (0, 200, 0) if rows[-1]["correct"] else (0, 0, 255)
            vis = cv2.copyMakeBorder(cv2.resize(vis, (180, 320)), 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=colour)
            tiles.append(vis)

    tp_good = sum(r["truth"] == "good" and r["pred"] == "PASS" for r in rows)
    fn_good = sum(r["truth"] == "good" and r["pred"] == "FAIL" for r in rows)       # false reject
    fp_def = sum(r["truth"] == "defective" and r["pred"] == "PASS" for r in rows)    # false PASS
    tn_def = sum(r["truth"] == "defective" and r["pred"] == "FAIL" for r in rows)
    n_def, n_good = fp_def + tn_def, tp_good + fn_good
    res = {"dir": args.dir, "parts": len(rows), "good": n_good, "defective": n_def,
           "confusion": {"good->PASS": tp_good, "good->FAIL (false reject)": fn_good,
                         "defective->PASS (FALSE PASS)": fp_def, "defective->FAIL": tn_def},
           "correct": tp_good + tn_def, "accuracy": round((tp_good + tn_def) / len(rows), 3),
           "false_pass_rate": round(fp_def / n_def, 3) if n_def else None,
           "false_reject_rate": round(fn_good / n_good, 3) if n_good else None,
           "target_false_pass_rate_max": 0.10, "headline": f"{tp_good + tn_def}/{len(rows)} parts correct",
           "per_defect": {k: {"n": sum(r["defect"] == k for r in rows),
                              "caught": sum(r["defect"] == k and r["pred"] == "FAIL" for r in rows)}
                          for k in sorted({r["defect"] for r in rows if r["defect"]})},
           "uses_simulated_images": any(r["source"] == "SIMULATED" for r in rows)}
    write_json("M5", "passfail", res)
    write_csv("M5", "passfail_results", rows)

    cm = np.array([[tp_good, fn_good], [fp_def, tn_def]])
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(v), ha="center", va="center", fontsize=16, color="black")
    ax.set_xticks([0, 1], ["PASS", "FAIL"])
    ax.set_yticks([0, 1], ["good", "defective"])
    ax.set_xlabel("station verdict")
    ax.set_ylabel("truth")
    ax.set_title(f"{res['headline']}, false-pass {res['false_pass_rate']}")
    fig.tight_layout()
    fig.savefig(evidence_dir("M5") / "passfail_confusion.png", dpi=120)
    while len(tiles) % 10:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(evidence_dir("M5") / "passfail_sheet.jpg"),
                np.vstack([np.hstack(tiles[r:r + 10]) for r in range(0, len(tiles), 10)]))
    print(json.dumps({k: res[k] for k in ("headline", "confusion", "false_pass_rate", "false_reject_rate", "per_defect")}, indent=1))


if __name__ == "__main__":
    main()
