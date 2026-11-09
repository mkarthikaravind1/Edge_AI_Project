"""Offline label review tool (OpenCV window, nothing leaves the laptop).

    python scripts/review_labels.py                 # starts at the first frame I have not reviewed
    python scripts/review_labels.py --start 40
    python scripts/review_labels.py --only exclude          # only the frames listed in data/labelled/exclude.txt
    python scripts/review_labels.py --only clip1_000854 clip1_000875

Mouse
  left-drag on empty space  draw a new box (current class)
  left-click on a box       select it (thick border)
  right-click on a box      delete it
Keys
  1 / 2 / 3     class enclosure / body / lid  (changes the selected box AND the class for new boxes)
  d             delete selected box
  c             clear all boxes on this image (image with no part)
  SPACE / n     accept this image as reviewed -> next
  p             previous image
  q / ESC       save and quit
Every accepted image is listed in data/labelled/reviewed.csv with a timestamp.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]
COLOURS = [(0, 220, 255), (60, 220, 60), (60, 60, 255)]


def write_reviewed(path: Path, reviewed: dict[str, dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "reviewed_at", "reviewer"])
        w.writerows([k, v["reviewed_at"], v["reviewer"]] for k, v in sorted(reviewed.items()))


class Review:
    def __init__(self, images: list[Path], lbl_dir: Path, reviewed_csv: Path, max_h: int,
                 reviewer: str = "karthik") -> None:
        self.images, self.lbl_dir, self.reviewed_csv = images, lbl_dir, reviewed_csv
        self.reviewer = reviewer
        self.reviewed: dict[str, dict[str, str]] = {}   # file -> {reviewed_at, reviewer}
        if reviewed_csv.exists():
            with open(reviewed_csv, newline="") as f:
                self.reviewed = {r["file"]: {"reviewed_at": r["reviewed_at"], "reviewer": r.get("reviewer", "")}
                                 for r in csv.DictReader(f)}
        self.max_h = max_h
        self.cur_cls = 0
        self.sel: int | None = None
        self.drag: tuple[int, int] | None = None
        self.mouse = (0, 0)
        self.boxes: list[list[float]] = []   # [cls, x1, y1, x2, y2] in image pixels
        self.i = 0

    # ---------- io ----------
    def load(self) -> None:
        p = self.images[self.i]
        self.img = cv2.imread(str(p))
        self.h, self.w = self.img.shape[:2]
        self.scale = min(2.0, self.max_h / self.h)
        self.boxes, self.sel = [], None
        lf = self.lbl_dir / f"{p.stem}.txt"
        if lf.exists():
            for line in lf.read_text().splitlines():
                if line.strip():
                    c, x, y, bw, bh = map(float, line.split())
                    self.boxes.append([int(c), (x - bw / 2) * self.w, (y - bh / 2) * self.h,
                                       (x + bw / 2) * self.w, (y + bh / 2) * self.h])

    def save(self) -> None:
        p = self.images[self.i]
        lines = []
        for c, x1, y1, x2, y2 in self.boxes:
            x1, x2 = sorted((np.clip(x1, 0, self.w), np.clip(x2, 0, self.w)))
            y1, y2 = sorted((np.clip(y1, 0, self.h), np.clip(y2, 0, self.h)))
            if x2 - x1 < 3 or y2 - y1 < 3:
                continue
            lines.append(f"{int(c)} {(x1 + x2) / 2 / self.w:.6f} {(y1 + y2) / 2 / self.h:.6f} "
                         f"{(x2 - x1) / self.w:.6f} {(y2 - y1) / self.h:.6f}\n")
        (self.lbl_dir / f"{p.stem}.txt").write_text("".join(lines))

    def mark_reviewed(self) -> None:
        self.reviewed[self.images[self.i].name] = {"reviewed_at": datetime.now().isoformat(timespec="seconds"),
                                                   "reviewer": self.reviewer}
        write_reviewed(self.reviewed_csv, self.reviewed)

    # ---------- interaction ----------
    def hit(self, x: float, y: float) -> int | None:
        inside = [(abs((b[3] - b[1]) * (b[4] - b[2])), k) for k, b in enumerate(self.boxes)
                  if b[1] <= x <= b[3] and b[2] <= y <= b[4]]
        return min(inside)[1] if inside else None

    def on_mouse(self, ev: int, mx: int, my: int, flags: int, _: object) -> None:
        x, y = mx / self.scale, my / self.scale
        self.mouse = (x, y)
        if ev == cv2.EVENT_LBUTTONDOWN:
            k = self.hit(x, y)
            if k is not None:
                self.sel = k
            else:
                self.drag = (x, y)
        elif ev == cv2.EVENT_LBUTTONUP and self.drag:
            x0, y0 = self.drag
            self.drag = None
            if abs(x - x0) > 5 and abs(y - y0) > 5:
                self.boxes.append([self.cur_cls, min(x0, x), min(y0, y), max(x0, x), max(y0, y)])
                self.sel = len(self.boxes) - 1
        elif ev == cv2.EVENT_RBUTTONDOWN:
            k = self.hit(x, y)
            if k is not None:
                self.boxes.pop(k)
                self.sel = None

    def render(self) -> np.ndarray:
        s = self.scale
        out = cv2.resize(self.img, (int(self.w * s), int(self.h * s)))
        for k, (c, x1, y1, x2, y2) in enumerate(self.boxes):
            col = COLOURS[int(c)]
            cv2.rectangle(out, (int(x1 * s), int(y1 * s)), (int(x2 * s), int(y2 * s)), col, 4 if k == self.sel else 2)
            cv2.putText(out, CLASSES[int(c)], (int(x1 * s) + 3, int(y1 * s) + 18), 0, 0.6, col, 2)
        if self.drag:
            x0, y0 = self.drag
            cv2.rectangle(out, (int(x0 * s), int(y0 * s)), (int(self.mouse[0] * s), int(self.mouse[1] * s)),
                          COLOURS[self.cur_cls], 1)
        name = self.images[self.i].name
        status = (f"{self.i + 1}/{len(self.images)}  reviewed {len(self.reviewed)}  "
                  f"{'[DONE]' if name in self.reviewed else '[todo]'}  new box: {self.cur_cls + 1}={CLASSES[self.cur_cls]}")
        bar = np.zeros((48, out.shape[1], 3), np.uint8)
        cv2.putText(bar, status, (6, 18), 0, 0.5, (255, 255, 255), 1)
        cv2.putText(bar, "1/2/3 class  d del  c clear  SPACE ok+next  p prev  q quit", (6, 40), 0, 0.45, (180, 180, 180), 1)
        return np.vstack([out, bar])

    def run(self, start: int | None) -> None:
        if start is not None:
            self.i = start
        else:
            todo = [k for k, p in enumerate(self.images) if p.name not in self.reviewed]
            self.i = todo[0] if todo else 0
        win = "review labels"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(win, self.on_mouse)
        self.load()
        while True:
            cv2.imshow(win, self.render())
            k = cv2.waitKey(20) & 0xFF
            if k in (ord("1"), ord("2"), ord("3")):
                self.cur_cls = k - ord("1")
                if self.sel is not None:
                    self.boxes[self.sel][0] = self.cur_cls
            elif k == ord("d") and self.sel is not None:
                self.boxes.pop(self.sel)
                self.sel = None
            elif k == ord("c"):
                self.boxes, self.sel = [], None
            elif k in (ord(" "), ord("n")):
                self.save()
                self.mark_reviewed()
                if self.i < len(self.images) - 1:
                    self.i += 1
                    self.load()
            elif k == ord("p") and self.i > 0:
                self.save()
                self.i -= 1
                self.load()
            elif k in (ord("q"), 27):
                self.save()
                break
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                self.save()
                break
        cv2.destroyAllWindows()
        print(f"reviewed {len(self.reviewed)}/{len(self.images)} images")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="data/frames/images")
    ap.add_argument("--labels", default="data/labelled")
    ap.add_argument("--start", type=int, default=None, help="index to start at (default: first unreviewed)")
    ap.add_argument("--height", type=int, default=640, help="window image height in pixels")
    ap.add_argument("--reviewer", default="karthik", help="name written to reviewed.csv")
    ap.add_argument("--only", nargs="+", default=None,
                    help="review only these frames (e.g. clip1_000854.jpg or clip1_000854), "
                         "or 'exclude' for every frame listed in exclude.txt")
    args = ap.parse_args()
    images = sorted(p for p in (ROOT / args.images).glob("*") if p.suffix.lower() in {".jpg", ".png", ".jpeg"})
    root = ROOT / args.labels
    if args.only:
        wanted: set[str] = set()
        for name in args.only:
            if name == "exclude":
                for line in (root / "exclude.txt").read_text(encoding="utf-8").splitlines():
                    line = line.split("#")[0].strip()
                    if line:
                        wanted.add(Path(line).stem)
            else:
                wanted.add(Path(name).stem)
        images = [p for p in images if p.stem in wanted]
        missing = wanted - {p.stem for p in images}
        if missing:
            print(f"not found in {args.images}: {', '.join(sorted(missing))}")
        if not images:
            return
        print(f"reviewing only {len(images)} frame(s): {', '.join(p.name for p in images)}")
        args.start = 0 if args.start is None else args.start
    (root / "labels").mkdir(parents=True, exist_ok=True)
    Review(images, root / "labels", root / "reviewed.csv", args.height, args.reviewer).run(args.start)


if __name__ == "__main__":
    main()
