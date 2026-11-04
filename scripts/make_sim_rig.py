"""Laptop stand-in for the rig image set until the Pi + rig exist (clearly marked in the manifest).

Real frames from clip1 (desk shots, no hands, WHOLE part in view - like a rig photo) for GOOD parts and for the real
defects (open body = lid missing, lid half slid on = lid not seated); surface marks and chipped corners are SIMULATED
by drawing on other real frames.
    calib_good/        good frames from 68-74.5 s of the video (calibration only)
    test/good/         10 good from 0-12.5 s (a minute away from calibration: no near-duplicates)
    test/defective/    10 defective (3 mark-sim, 2 chip-sim, 3 lid_missing real, 2 lid_not_seated real)

    python scripts/make_sim_rig.py   -> data/rig_sim/ + data/rig_sim/manifest.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from edgevision.config import load_config
from edgevision.detect import make_detector


ROOT = Path(__file__).resolve().parents[1]
FR = sorted((ROOT / "data/frames/images").glob("*.jpg"))
# indices into the sorted 217 extracted frames, picked from the contact sheets: closed box on the desk, no hands
CALIB_SECONDS = (68.0, 74.5)                 # calibration frames come straight from this stretch of clip1
TEST_GOOD = [0, 1, 11, 20, 21, 23, 26, 29, 31, 32]   # whole part in view, 0-12.5 s
MARK_SRC = [12, 22, 198]
CHIP_SRC = [28, 30]
LID_MISSING = [172, 174, 175]
LID_NOT_SEATED = [177, 178]


def draw_mark(img: np.ndarray, box: tuple, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x1, y1, x2, y2 = map(int, box)
    out = img.copy()
    cx, cy = int(x1 + (x2 - x1) * rng.uniform(0.35, 0.65)), int(y1 + (y2 - y1) * rng.uniform(0.35, 0.6))
    s = int(0.07 * min(x2 - x1, y2 - y1)) + 4
    pts = np.array([[cx + rng.integers(-s, s), cy + rng.integers(-s, s)] for _ in range(5)], np.int32)
    cv2.polylines(out, [pts], False, (35, 35, 40), thickness=max(3, s // 3), lineType=cv2.LINE_AA)   # marker scribble
    return out


def cut_corner(img: np.ndarray, box: tuple) -> np.ndarray:
    """Paint a triangle of background colour over the part's left-most corner (as if a corner broke off)."""
    x1, y1, x2, y2 = map(int, box)
    out = img.copy()
    g = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(cv2.GaussianBlur(g, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    corner = c[c[:, :, 0].argmin()][0] + [x1, y1]                 # left-most point of the outline
    s = int(0.28 * min(x2 - x1, y2 - y1))
    strip = img[max(0, y1 - 25):y1, x1:x2].reshape(-1, 3)
    bg = tuple(int(v) for v in np.median(strip, 0)) if strip.size else (90, 110, 130)
    tri = np.array([corner, corner + [s, -s // 2], corner + [s, s // 2]], np.int32)
    cv2.fillConvexPoly(out, tri, bg, lineType=cv2.LINE_AA)
    return out


def main() -> None:
    out = ROOT / "data/rig_sim"
    shutil.rmtree(out, ignore_errors=True)
    cfg = load_config()
    det = make_detector(cfg["detector"], cfg["classes"])
    man = []

    def save(img, sub, name, kind, label, defect=None):
        p = out / sub / name
        p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(p), img)
        man.append({"file": f"{sub}/{name}", "source": kind, "label": label, "defect": defect})

    def enc_box(img):
        e = [d for d in det.detect(img) if d.name == "enclosure"]
        return max(e, key=lambda d: d.conf).box if e else None

    cap = cv2.VideoCapture(str(ROOT / "data/raw/videos/clip1.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    for k in range(int(CALIB_SECONDS[0] * fps), int(CALIB_SECONDS[1] * fps), 5):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, img = cap.read()
        if not ok or cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var() < 60:
            continue                                                  # same blur gate as the dataset
        b = enc_box(img)
        h, w = img.shape[:2]
        if b is None or b[0] <= 3 or b[1] <= 3 or b[2] >= w - 4 or b[3] >= h - 4:
            continue                                                  # rig photos show the whole part
        save(img, "calib_good", f"calib_{k:05d}.jpg", "real", "good")
    for i in TEST_GOOD:
        save(cv2.imread(str(FR[i])), "test/good", FR[i].name, "real", "good")
    for k, i in enumerate(MARK_SRC):
        img = cv2.imread(str(FR[i]))
        save(draw_mark(img, enc_box(img), k), "test/defective", f"mark_sim_{FR[i].name}", "SIMULATED", "defective", "surface_mark")
    for i in CHIP_SRC:
        img = cv2.imread(str(FR[i]))
        save(cut_corner(img, enc_box(img)), "test/defective", f"chip_sim_{FR[i].name}", "SIMULATED", "defective", "chipped_corner")
    for i in LID_MISSING:
        save(cv2.imread(str(FR[i])), "test/defective", f"lidmissing_{FR[i].name}", "real", "defective", "lid_missing")
    for i in LID_NOT_SEATED:
        save(cv2.imread(str(FR[i])), "test/defective", f"lidnotseated_{FR[i].name}", "real", "defective", "lid_not_seated")
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    print({s: sum(m["file"].startswith(s) for m in man) for s in ("calib_good", "test/good", "test/defective")})
    tiles = []
    for m in man:
        im = cv2.imread(str(out / m["file"]))
        im = cv2.resize(im, (180, 320))
        cv2.putText(im, (m["defect"] or m["label"])[:12], (3, 15), 0, 0.45, (0, 255, 255), 1)
        tiles.append(im)
    while len(tiles) % 8:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(out / "contact_sheet.jpg"), np.vstack([np.hstack(tiles[r:r + 8]) for r in range(0, len(tiles), 8)]))


if __name__ == "__main__":
    main()
