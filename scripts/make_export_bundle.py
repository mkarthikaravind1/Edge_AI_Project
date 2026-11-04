"""Zip what Colab needs to export TFLite (FP32 + INT8): my weights, the export script, and train-split
calibration images (real frames + renders, no augmented copies). TFLite export only runs on Linux/macOS.

    python scripts/make_export_bundle.py   -> export_bundle.zip  (upload in scripts/export_colab.ipynb)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = ROOT / "export_bundle.zip"
    imgs = [p for p in sorted((ROOT / "data/splits/train/images").glob("*.jpg")) if not p.stem.startswith("aug_")]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("models/best.pt", "scripts/export.py"):
            z.write(ROOT / f, f)
        for p in imgs:
            z.write(p, p.relative_to(ROOT).as_posix())
            lbl = ROOT / "data/splits/train/labels" / f"{p.stem}.txt"
            if lbl.exists():
                z.write(lbl, lbl.relative_to(ROOT).as_posix())
    print(f"{out.name}: {len(imgs)} calibration-pool images, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
