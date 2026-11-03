"""Zip everything Colab needs (splits + data.yaml + scripts + targets) into colab_bundle.zip.

    python scripts/make_colab_bundle.py      -> upload colab_bundle.zip in the notebook
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = ROOT / "colab_bundle.zip"
    splits = ROOT / "data/splits"
    if not (splits / "data.yaml").exists():
        raise SystemExit("run scripts/split.py first")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in splits.rglob("*"):
            if p.is_file():
                arc = p.relative_to(ROOT).as_posix()
                if p.name == "data.yaml":
                    text = p.read_text().splitlines()
                    text[0] = "path: /content/bundle/data/splits"
                    z.writestr(arc, "\n".join(text) + "\n")
                else:
                    z.write(p, arc)
                n += 1
        for s in ("scripts/wrong_detections.py", "docs/targets.json"):
            if (ROOT / s).exists():
                z.write(ROOT / s, s)
    print(f"{out.name}: {n} data files, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
