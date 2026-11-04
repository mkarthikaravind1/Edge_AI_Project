"""M3.3: show that ONE bad frame does not trigger and N frames in a row do - with the real detector on real images.

Frame sequence fed through the real model + DecisionEngine:
  empty x6 | part x1 (single glitch) | empty x6 | part x7 (one part, N in a row) | empty 2.5 s | part x3 (next part)
"empty" = a frame of plain background (no part); "part" = a real test image with a closed enclosure.

    python scripts/debounce_demo.py      -> evidence/M3/debounce_demo.csv + .json
"""

from __future__ import annotations

from pathlib import Path

import cv2

from edgevision.config import load_config
from edgevision.decide import DecisionEngine, Event
from edgevision.detect import make_detector
from edgevision.evidence import write_csv, write_json
from edgevision.hal import ConsoleActuator

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = load_config()
    d = cfg["decide"]
    det = make_detector(cfg["detector"], cfg["classes"])
    t = [0.0]
    engine = DecisionEngine.from_config(d, clock=lambda: t[0])
    reject = ConsoleActuator("reject", quiet=True)

    part_img = next(cv2.imread(str(p)) for p in sorted((ROOT / "data/splits/test/images").glob("*.jpg"))
                    if any(x.name in d["trigger_classes"] and x.conf >= d["conf_threshold"]
                           for x in det.detect(cv2.imread(str(p)))))
    empty_img = cv2.GaussianBlur(part_img, (0, 0), 60)           # same colours, no object shape = "no part"

    fps = 15
    gap = int(2.5 * fps)                                         # longer than cooldown_s: a new part arrives
    seq = ["empty"] * 6 + ["part"] + ["empty"] * 6 + ["part"] * 7 + ["empty"] * gap + ["part"] * 3
    glitch = 6
    burst1 = 13 + d["n"] - 1                                     # N-th consecutive hit of the first part
    burst2 = 13 + 7 + gap + d["n"] - 1                           # N-th hit of the next part
    rows, triggers = [], []
    for i, kind in enumerate(seq):
        t[0] += 1 / fps
        dets = det.detect(part_img if kind == "part" else empty_img)
        dec = engine.on_frame(dets)
        if dec.event == Event.TRIGGER:
            reject.pulse(0.01, "demo")
            triggers.append(i)
        best = max((x.conf for x in dets if x.name in d["trigger_classes"]), default=0.0)
        rows.append({"frame": i, "input": kind, "best_conf": round(best, 3), "hit": dec.hit,
                     "hits_in_last_m": dec.hits_in_window, "event": dec.event.value,
                     "reject_fired": dec.event == Event.TRIGGER})
        print(f"{i:2d} {kind:5s} conf={best:.2f} hit={int(dec.hit)} window={dec.hits_in_window}/{d['m']} -> {dec.event.value}")

    write_csv("M3", "debounce_demo", rows)
    res = {"rule": f"{d['n']}-of-{d['m']} hits with conf >= {d['conf_threshold']} on {d['trigger_classes']}",
           "rearm_on_clear": d.get("rearm_on_clear", True),
           "single_glitch_frame": glitch, "single_glitch_triggered": glitch in triggers,
           "trigger_frames": triggers,
           "fps": fps, "expected_trigger_frames": [burst1, burst2],
           "expected": f"no trigger at frame {glitch} (one bad frame); trigger at frame {burst1} ({d['n']}rd hit in a row); "
                       f"same part keeps HOLD; trigger again at frame {burst2} for the next part",
           "passed": glitch not in triggers and triggers == [burst1, burst2]}
    write_json("M3", "debounce_demo", res)
    print(res)


if __name__ == "__main__":
    main()
