"""Train a small HELPER model that only proposes labels (pass 2 of auto-labelling). Runs on the laptop CPU.

Data: the real frames I already reviewed + my CAD renders. Starts from public yolov8n.pt.
This model is NOT the submitted detector (that one is trained in Colab on the leak-free split);
it only pre-draws boxes that I then review, so it cannot leak test data into the final model.

    python scripts/train_prelabel.py --epochs 25
    python scripts/autolabel.py --model models/prelabel.pt
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["enclosure", "body", "lid"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--real-repeat", type=int, default=4, help="copies of each reviewed real frame (they are few)")
    ap.add_argument("--work", default="runs/prelabel_data")
    args = ap.parse_args()

    with open(ROOT / "data/labelled/reviewed.csv", newline="") as f:
        reviewed = [r["file"] for r in csv.DictReader(f)]
    if len(reviewed) < 15:
        raise SystemExit(f"only {len(reviewed)} reviewed frames - review at least ~25 first")

    work = ROOT / args.work
    if work.exists():
        shutil.rmtree(work)
    for s in ("train", "val"):
        (work / s / "images").mkdir(parents=True)
        (work / s / "labels").mkdir(parents=True)
    # every 5th reviewed frame -> val so I can see if the helper is any good
    for k, name in enumerate(sorted(reviewed)):
        stem = Path(name).stem
        split = "val" if k % 5 == 0 else "train"
        reps = 1 if split == "val" else args.real_repeat
        for r in range(reps):
            shutil.copy2(ROOT / "data/frames/images" / name, work / split / "images" / f"r{r}_{name}")
            shutil.copy2(ROOT / "data/labelled/labels" / f"{stem}.txt", work / split / "labels" / f"r{r}_{stem}.txt")
    for p in (ROOT / "data/synthetic/images").glob("*.jpg"):
        shutil.copy2(p, work / "train" / "images" / p.name)
        shutil.copy2(ROOT / "data/synthetic/labels" / f"{p.stem}.txt", work / "train" / "labels" / f"{p.stem}.txt")
    (work / "data.yaml").write_text(f"path: {work.as_posix()}\ntrain: train/images\nval: val/images\nnames:\n"
                                    + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))

    from ultralytics import YOLO

    m = YOLO("yolov8n.pt")
    m.train(data=str(work / "data.yaml"), epochs=args.epochs, imgsz=args.imgsz, batch=16, device="cpu",
            workers=0, project=str(ROOT / "runs"), name="prelabel", exist_ok=True, plots=False, verbose=False)
    r = m.val(data=str(work / "data.yaml"), imgsz=args.imgsz, device="cpu", verbose=False, plots=False)
    (ROOT / "models").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "runs/prelabel/weights/best.pt", ROOT / "models/prelabel.pt")
    res = {"purpose": "label-assist only, not the submitted model", "reviewed_real_frames": len(reviewed),
           "epochs": args.epochs, "imgsz": args.imgsz,
           "val_on_reviewed_real": {"mAP50": round(float(r.box.map50), 3), "mAP50_95": round(float(r.box.map), 3)}}
    (ROOT / "evidence/M1/prelabel_model.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
