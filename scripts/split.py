"""Leak-free 70/20/10 split.

Real frames: each video is cut into contiguous TIME BLOCKS; whole blocks go to train/val/test,
and frames within --gap-s of a block boundary between different splits are dropped, so two
almost identical neighbouring frames can never land in different splits.
Synthetic renders: grouped by render seed block; train/val only (the test set is real images only).
Finally every val/test image is pHash-compared with every train image to prove no duplicates leaked.

    python scripts/split.py
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
SPLITS = ("train", "val", "test")


def read_manifest(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _apply_blocks(rs: list[dict], labels: list[str], gap_s: float) -> tuple[dict[str, str], list[float], int]:
    n = len(labels)
    t0, t1 = float(rs[0]["timestamp_s"]), float(rs[-1]["timestamp_s"]) + 1e-6
    edges = np.linspace(t0, t1, n + 1)
    assign, dropped = {}, 0
    for r in rs:
        t = float(r["timestamp_s"])
        b = min(int(np.searchsorted(edges, t, side="right")) - 1, n - 1)
        near_prev = b > 0 and labels[b - 1] != labels[b] and t - edges[b] < gap_s
        near_next = b < n - 1 and labels[b + 1] != labels[b] and edges[b + 1] - t < gap_s
        if near_prev or near_next:
            dropped += 1
            continue
        assign[r["file"]] = labels[b]
    return assign, [round(float(e), 2) for e in edges], dropped


def assign_real(rows: list[dict], n_blocks: int, gap_s: float, rng: np.random.Generator,
                classes_of: dict[str, set[str]], tries: int = 500) -> tuple[dict[str, str], dict]:
    """Whole time blocks go to one split. Among `tries` random block assignments, keep the one where
    val and test contain every class and the real-image ratio is closest to 70/20/10."""
    by_video: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_video[r["video"]].append(r)
    for rs in by_video.values():
        rs.sort(key=lambda r: float(r["timestamp_s"]))
    k_test = max(1, round(0.1 * n_blocks))
    k_val = max(1, round(0.2 * n_blocks))
    base = ["test"] * k_test + ["val"] * k_val + ["train"] * (n_blocks - k_test - k_val)
    target = {"train": 0.7, "val": 0.2, "test": 0.1}
    all_classes = set().union(*classes_of.values()) if classes_of else set()

    best = None
    for _ in range(tries):
        assign, info = {}, {}
        for vid, rs in sorted(by_video.items()):
            labels = [str(x) for x in rng.permutation(base)]
            a, edges, dropped = _apply_blocks(rs, labels, gap_s)
            assign.update(a)
            info[vid] = {"blocks": labels, "block_edges_s": edges, "dropped_at_boundaries": dropped}
        n = max(1, len(assign))
        missing = sum(len(all_classes - set().union(*[classes_of.get(f, set()) for f, s in assign.items() if s == sp]))
                      for sp in ("val", "test"))
        ratio_err = sum(abs(sum(s == sp for s in assign.values()) / n - target[sp]) for sp in target)
        score = (missing, ratio_err)
        if best is None or score < best[0]:
            best = (score, assign, info)
    (missing, ratio_err), assign, info = best
    info["_selection"] = {"tries": tries, "classes_missing_in_val_test": missing, "ratio_error": round(ratio_err, 3)}
    return assign, info


def assign_synthetic(rows: list[dict], rng: np.random.Generator, val_frac: float = 0.2) -> dict[str, str]:
    groups = sorted({r["group"] for r in rows})
    val_groups = set(rng.choice(groups, max(1, round(val_frac * len(groups))), replace=False)) if groups else set()
    return {r["file"]: ("val" if r["group"] in val_groups else "train") for r in rows}


def label_counts(lbl: Path) -> Counter:
    c: Counter = Counter()
    if lbl.exists():
        for line in lbl.read_text().splitlines():
            if line.strip():
                c[CLASSES[int(line.split()[0])]] += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-images", default="data/frames/images")
    ap.add_argument("--real-labels", default="data/labelled/labels")
    ap.add_argument("--real-manifest", default="data/frames/manifest.csv")
    ap.add_argument("--syn-dir", default="data/synthetic")
    ap.add_argument("--out", default="data/splits")
    ap.add_argument("--blocks", type=int, default=20, help="time blocks per video")
    ap.add_argument("--gap-s", type=float, default=0.5, help="drop frames this close to a split boundary")
    ap.add_argument("--dup-max", type=int, default=4, help="pHash distance treated as a leaked duplicate")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-synthetic", action="store_true")
    ap.add_argument("--include-unreviewed", action="store_true", help="also use auto-labels I have not checked (tests only)")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    manifest = read_manifest(ROOT / args.real_manifest)
    real_rows = [r for r in manifest if (ROOT / args.real_labels / (Path(r["file"]).stem + ".txt")).exists()]
    reviewed_csv = ROOT / args.real_labels / ".." / "reviewed.csv"
    if not args.include_unreviewed:
        reviewed = {r["file"] for r in read_manifest(reviewed_csv)}
        skipped = len(real_rows) - sum(r["file"] in reviewed for r in real_rows)
        real_rows = [r for r in real_rows if r["file"] in reviewed]
        print(f"using {len(real_rows)} reviewed real frames ({skipped} unreviewed skipped)")
    exclude_txt = ROOT / args.real_labels / ".." / "exclude.txt"
    excluded = set()
    if exclude_txt.exists():
        excluded = {l.split("#")[0].strip() for l in exclude_txt.read_text().splitlines()} - {""}
        real_rows = [r for r in real_rows if r["file"] not in excluded]
        print(f"excluded {len(excluded)} frames listed in exclude.txt (labels still to fix)")
    syn_dir = ROOT / args.syn_dir
    syn_rows = [] if args.no_synthetic else read_manifest(syn_dir / "manifest.csv")
    classes_of = {r["file"]: set(label_counts(ROOT / args.real_labels / (Path(r["file"]).stem + ".txt")))
                  for r in real_rows}
    real_assign, block_info = assign_real(real_rows, args.blocks, args.gap_s, rng, classes_of)
    syn_assign = assign_synthetic(syn_rows, rng)

    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    items = [(f, s, ROOT / args.real_images / f, ROOT / args.real_labels / (Path(f).stem + ".txt"), "real")
             for f, s in real_assign.items()]
    items += [(f, s, syn_dir / "images" / f, syn_dir / "labels" / (Path(f).stem + ".txt"), "synthetic")
              for f, s in syn_assign.items()]

    counts = {s: {"real": 0, "synthetic": 0, "boxes": Counter()} for s in SPLITS}
    hashes: dict[str, list[tuple[str, imagehash.ImageHash]]] = {s: [] for s in SPLITS}
    for f, s, img, lbl, src in items:
        for sub in ("images", "labels"):
            (out / s / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, out / s / "images" / f)
        if lbl.exists():
            shutil.copy2(lbl, out / s / "labels" / lbl.name)
        else:
            (out / s / "labels" / lbl.name).write_text("")
        counts[s][src] += 1
        counts[s]["boxes"] += label_counts(lbl)
        hashes[s].append((f, imagehash.phash(Image.open(img))))

    leaks = []
    train_h = np.array([h.hash.flatten() for _, h in hashes["train"]]) if hashes["train"] else np.zeros((0, 64), bool)
    for s in ("val", "test"):
        for f, h in hashes[s]:
            if len(train_h):
                d = (train_h != h.hash.flatten()).sum(1)
                j = int(d.argmin())
                if d[j] <= args.dup_max:
                    leaks.append({"split": s, "file": f, "train_match": hashes["train"][j][0], "distance": int(d[j])})

    (out / "data.yaml").write_text(
        f"path: {out.as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        f"names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))

    total = sum(counts[s]["real"] + counts[s]["synthetic"] for s in SPLITS)
    real_total = sum(counts[s]["real"] for s in SPLITS)
    report = {
        "method": "real: contiguous time blocks per video (+ boundary gap); synthetic: render-seed groups, train/val only",
        "params": vars(args),
        "splits": {s: {"real": counts[s]["real"], "synthetic": counts[s]["synthetic"],
                       "real_pct": round(100 * counts[s]["real"] / real_total, 1) if real_total else 0,
                       "boxes": dict(counts[s]["boxes"])} for s in SPLITS},
        "total_images": total,
        "real_blocks": block_info,
        "cross_split_duplicates": {"checked_pairs": "every val/test image vs every train image (pHash)",
                                   "threshold": args.dup_max, "found": len(leaks), "items": leaks[:50]},
        "test_is_real_only": counts["test"]["synthetic"] == 0,
        "only_reviewed_labels": not args.include_unreviewed,
        "excluded_frames": sorted(excluded),
    }
    ev = ROOT / "evidence/M1"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "split_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["splits"], indent=2))
    print(f"duplicates across splits: {len(leaks)}  -> evidence/M1/split_report.json")


if __name__ == "__main__":
    main()
