"""Render synthetic, auto-labelled YOLO images of my enclosure from my STL files:
the closed box (enclosure), Model 1 (body) and Model 2 (lid).

No Blender needed: a small flat-shaded rasteriser (numpy + OpenCV) with
random pose, distance, light, PLA colour, background and distractors. Boxes come from the
final per-object pixel mask, so occlusion is handled correctly.

    python scripts/render_cad.py --n 400 --out data/synthetic
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
LID_SEAT_MM = -6.0   # lid groove (y 14.45-16.45) slides onto the body rail (y 8.45-10.45)
PLA_COLOURS = {   # BGR, rough PLA shades
    "white": (235, 235, 235), "grey": (150, 150, 150), "black": (45, 45, 45),
    "red": (50, 50, 200), "blue": (190, 110, 40), "yellow": (60, 210, 230),
    "green": (80, 170, 60), "orange": (40, 130, 240),
}


def load_parts() -> dict[str, trimesh.Trimesh]:
    body = trimesh.load(ROOT / "cad/model1_body.stl")
    lid = trimesh.load(ROOT / "cad/model2_lid.stl")
    seated = lid.copy()
    seated.apply_translation([0, LID_SEAT_MM, 0])
    return {"body": body, "lid": lid, "lid_seated": seated}


def background(rng: np.random.Generator, h: int, w: int, bg_files: list[Path]) -> np.ndarray:
    if bg_files and rng.random() < 0.7:
        img = cv2.imread(str(bg_files[rng.integers(len(bg_files))]))
        if img is not None:
            y = rng.integers(0, max(1, img.shape[0] - h // 2))
            x = rng.integers(0, max(1, img.shape[1] - w // 2))
            crop = img[y:, x:]
            return cv2.resize(crop, (w, h))
    c1, c2 = rng.integers(20, 235, 3), rng.integers(20, 235, 3)
    t = np.linspace(0, 1, w if rng.random() < 0.5 else h)
    grad = (c1[None] * (1 - t[:, None]) + c2[None] * t[:, None]).astype(np.uint8)
    img = np.repeat(grad[None], h, 0) if grad.shape[0] == w else np.repeat(grad[:, None], w, 1)
    img = img.copy()
    noise = rng.normal(0, rng.uniform(2, 18), (h, w, 1))
    img = np.clip(img + noise, 0, 255).astype(np.uint8)
    for _ in range(rng.integers(0, 6)):          # distractor shapes (tape, pens, paper ...)
        col = tuple(int(v) for v in rng.integers(0, 255, 3))
        if rng.random() < 0.5:
            p = rng.integers(0, [w, h], (2, 2))
            cv2.rectangle(img, tuple(int(v) for v in p[0]), tuple(int(v) for v in p[1]), col, -1)
        else:
            cv2.circle(img, (int(rng.integers(w)), int(rng.integers(h))), int(rng.integers(5, 60)), col, -1)
    return cv2.GaussianBlur(img, (0, 0), rng.uniform(0.1, 1.5))


def render(rng: np.random.Generator, parts: dict[str, trimesh.Trimesh], w: int, h: int,
           bg_files: list[Path], colour_names: list[str]) -> tuple[np.ndarray, list[tuple[int, list[float]]], dict]:
    ss = 2                                    # supersampling for anti-aliased edges
    W, H = w * ss, h * ss
    f = rng.uniform(500, 800) * ss
    cx, cy = W / 2, H / 2

    # A group is rendered as one rigid object; parts in a group share one box and one class.
    closed = [("enclosure", parts["body"]), ("enclosure", parts["lid_seated"])]
    mode = str(rng.choice(["assembled", "separate", "body", "lid", "mixed"], p=[0.3, 0.3, 0.15, 0.15, 0.1]))
    if mode == "assembled":
        groups = [closed]
    elif mode == "separate":
        groups = [[("body", parts["body"])], [("lid", parts["lid"])]]
    elif mode == "mixed":            # my second print: one closed box next to loose parts
        groups = [closed, [("body", parts["body"])], [("lid", parts["lid"])]][: int(rng.integers(2, 4))]
    else:
        groups = [[(mode, parts[mode])]]

    light = rng.normal(size=3)
    light[2] = -abs(light[2]) - 0.3            # light roughly from the camera side
    light /= np.linalg.norm(light)
    ambient = rng.uniform(0.25, 0.5)
    colour_name = str(rng.choice(colour_names))
    base = np.array(PLA_COLOURS[colour_name], float)

    tris, shades, ids = [], [], []
    slots = rng.permutation(4)[: len(groups)]  # place groups in different quadrants
    for gi, group in enumerate(groups):
        centre = np.mean([m.bounds.mean(0) for _, m in group], 0)
        rot = Rotation.random(random_state=int(rng.integers(1 << 31))).as_matrix()
        target_px = rng.uniform(0.18, 0.55 if len(groups) == 1 else 0.35) * W
        z = f * 50.0 / target_px
        if len(groups) == 1:
            u, v = rng.uniform(0.3, 0.7) * W, rng.uniform(0.3, 0.7) * H
        else:
            q = slots[gi]
            u = (0.25 + 0.5 * (q % 2) + rng.uniform(-0.08, 0.08)) * W
            v = (0.25 + 0.5 * (q // 2) + rng.uniform(-0.08, 0.08)) * H
        t = np.array([(u - cx) * z / f, (v - cy) * z / f, z])
        tint = base * rng.uniform(0.9, 1.1, 3)
        for name, mesh in group:
            verts = (mesh.vertices - centre) @ rot.T + t
            normals = mesh.face_normals @ rot.T
            tri = verts[mesh.faces]
            visible = np.einsum("ij,ij->i", normals, tri.mean(1)) < 0
            lam = ambient + (1 - ambient) * np.clip(normals @ light, 0, 1)   # light = direction towards the lamp
            tris.append(tri[visible])
            shades.append(np.clip(lam[visible, None] * tint, 0, 255))
            ids.append(np.full(visible.sum(), CLASSES.index(name) + 1 + 10 * gi))

    tri = np.concatenate(tris)
    shade = np.concatenate(shades)
    oid = np.concatenate(ids)
    order = np.argsort(-tri[:, :, 2].mean(1))   # painter's algorithm: far to near

    img = background(rng, H, W, bg_files)
    mask = np.zeros((H, W), np.int32)
    pts = np.stack([tri[:, :, 0] * f / tri[:, :, 2] + cx, tri[:, :, 1] * f / tri[:, :, 2] + cy], -1)

    # soft contact shadow first
    shadow = np.zeros((H, W), np.uint8)
    for i in order:
        cv2.fillConvexPoly(shadow, np.round(pts[i]).astype(np.int32), 255)
    off = (rng.integers(-15, 15) * ss, rng.integers(5, 25) * ss)
    shadow = np.roll(shadow, off, (1, 0))
    shadow = cv2.GaussianBlur(shadow, (0, 0), 8 * ss).astype(float) / 255 * rng.uniform(0.2, 0.5)
    img = (img * (1 - shadow[..., None])).astype(np.uint8)

    for i in order:
        p = np.round(pts[i]).astype(np.int32)
        cv2.fillConvexPoly(img, p, tuple(float(c) for c in shade[i]), lineType=cv2.LINE_AA)
        cv2.fillConvexPoly(mask, p, int(oid[i]))

    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST).astype(np.int32)

    # camera effects
    if rng.random() < 0.3:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.5, 1.5))
    img = np.clip(img * rng.uniform(0.7, 1.3) + rng.uniform(-25, 25) + rng.normal(0, rng.uniform(1, 6), img.shape), 0, 255).astype(np.uint8)
    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(60, 95))])
    img = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    labels = []
    for val in np.unique(mask):
        if val == 0:
            continue
        ys, xs = np.nonzero(mask == val)
        if len(xs) < 150:                       # too small/occluded to label reliably
            continue
        cls = int(val % 10) - 1
        x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        labels.append((cls, [(x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h]))
    return img, labels, {"mode": mode, "colour": colour_name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="number of images")
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--colours", default="white,white,white,white,white,white,grey,black,red,blue,yellow,green,orange",
                    help="comma list; my print is white, so it is repeated to weight it (~half the renders)")
    ap.add_argument("--backgrounds", default="data/backgrounds", help="folder of photos used as backgrounds")
    args = ap.parse_args()

    out = ROOT / args.out
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    bg_dir = ROOT / args.backgrounds
    bg_files = sorted(p for p in bg_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    colours = [c.strip() for c in args.colours.split(",") if c.strip() in PLA_COLOURS]
    parts = load_parts()

    rows = []
    for k in range(args.n):
        seed = args.seed + k
        rng = np.random.default_rng(seed)
        img, labels, meta = render(rng, parts, args.width, args.height, bg_files, colours)
        stem = f"syn_{seed:05d}"
        cv2.imwrite(str(out / "images" / f"{stem}.jpg"), img)
        with open(out / "labels" / f"{stem}.txt", "w") as f:
            for c, b in labels:
                f.write(f"{c} " + " ".join(f"{v:.6f}" for v in b) + "\n")
        rows.append({"file": f"{stem}.jpg", "source": "synthetic", "video": "render_cad", "seed": seed,
                     "group": seed // 25, "timestamp_s": "", "mode": meta["mode"], "colour": meta["colour"],
                     **{f"n_{n}": sum(c == i for c, _ in labels) for i, n in enumerate(CLASSES)}})
        if (k + 1) % 50 == 0:
            print(f"rendered {k + 1}/{args.n}", file=sys.stderr)

    with open(out / "manifest.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} images -> {out}  " + "  ".join(f"{n}={sum(r[f'n_{n}'] for r in rows)}" for n in CLASSES))


if __name__ == "__main__":
    main()
