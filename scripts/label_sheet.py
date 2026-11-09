"""Contact sheet of labelled images (boxes drawn from the YOLO label files), for the Dataset v1 evidence.

    python scripts/label_sheet.py                                   # real test split -> evidence/M1/labelled_samples.jpg
    python scripts/label_sheet.py --images data/splits/val/images --labels data/splits/val/labels --out evidence/M1/labelled_val.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
COLOURS = [(0, 220, 255), (60, 220, 60), (60, 60, 255)]   # BGR, same as review_labels.py


def draw(img: np.ndarray, label_file: Path) -> tuple[np.ndarray, int]:
    h, w = img.shape[:2]
    n = 0
    if label_file.exists():
        for line in label_file.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            c, xc, yc, bw, bh = int(parts[0]), *map(float, parts[1:])
            x1, y1 = int((xc - bw / 2) * w), int((yc - bh / 2) * h)
            x2, y2 = int((xc + bw / 2) * w), int((yc + bh / 2) * h)
            col = COLOURS[c % len(COLOURS)]
            cv2.rectangle(img, (x1, y1), (x2, y2), col, 3)
            cv2.putText(img, CLASSES[c], (x1 + 3, max(y1 - 6, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            n += 1
    return img, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="data/splits/test/images")
    ap.add_argument("--labels", default="data/splits/test/labels")
    ap.add_argument("--out", default="evidence/M1/labelled_samples.jpg")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--tile", type=int, default=300, help="tile height in px")
    a = ap.parse_args()

    images = sorted((ROOT / a.images).glob("*.jpg"))
    tiles = []
    for p in images:
        img, n = draw(cv2.imread(str(p)), ROOT / a.labels / f"{p.stem}.txt")
        s = a.tile / img.shape[0]
        img = cv2.resize(img, (int(img.shape[1] * s), a.tile))
        cv2.putText(img, f"{p.stem} ({n})", (6, a.tile - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        tiles.append(img)
    tw = max(t.shape[1] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 2, 2, 2, 2 + tw - t.shape[1], cv2.BORDER_CONSTANT, value=(40, 40, 40)) for t in tiles]
    while len(tiles) % a.cols:
        tiles.append(np.full_like(tiles[0], 40))
    rows = [np.hstack(tiles[i:i + a.cols]) for i in range(0, len(tiles), a.cols)]
    sheet = np.vstack(rows)
    out = ROOT / a.out
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{len(images)} images -> {out} ({sheet.shape[1]}x{sheet.shape[0]})")


if __name__ == "__main__":
    main()
