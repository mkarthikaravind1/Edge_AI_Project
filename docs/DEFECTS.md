# Good vs defective (M5 definition)

The station looks at a **closed enclosure from above at ~30–45°** (see [RIG.md](RIG.md)). From that view the lid
face, the outline and the lid seating are visible. The two sensor holes are on the **bottom** face and are hidden
when the lid is on, so "blocked hole" (my first draft, 3 Nov) cannot be inspected by a top camera and was replaced.

A part is **GOOD** when it is a closed enclosure, lid fully seated, outline intact, no marks.

| # | Defect | How it is detected (`src/edgevision/inspect.py`) | How I make the sample (no reprint) |
|---|---|---|---|
| D1 | **Surface mark** | dark blob on the part bigger than any on a good part (designed slot excluded by shape: long thin box) | marker dot / scribble, or a strip of black tape |
| D2 | **Chipped / broken corner** | outline less *solid* (area ÷ convex hull) or less rectangular than any good part | the older print, or snip a corner with cutters on a spare |
| D3 | **Lid missing** | the detector sees an open body (Model 1) and no closed enclosure | body without lid |
| D4 | **Lid not seated** | body + lid both seen overlapping, or the outline is broken by the step | lid pushed only half-way on |

Limits come only from **good** parts (`scripts/calibrate_inspection.py`): every limit is "worse than the worst good
part I calibrated on". A part is judged only when it is **fully in view** (box not touching the image border).
Per part, the station gives FAIL if ≥ 3 of the last 5 frames were FAIL (same debounce as M3), else PASS.

Pass/fail test set (M5.2): **10 good + 10 defective** (≥ 2 of each defect type), shot on the rig with
`scripts/capture_rig.py`. A **false pass** (defective classified GOOD) is the critical error; target ≤ 1 of 10.

## Laptop stand-in result (until the rig exists) — `evidence/M5/passfail.json`
Rig images replaced by desk frames from clip1 (real: good parts, lid missing, lid not seated; **simulated**: marks and
chips drawn on real frames — see `data/rig_sim/manifest.json`).

| Run | Correct | False-pass rate | Missed | Notes |
|---|---|---|---|---|
| v1 (rectangularity + vertices, slot counted as mark) | 16/20 | 0.30 | 2 chips, 1 mark | `evidence/M5/passfail_v1_before_fixes.json` |
| v2 (solidity, slot excluded, fully-in-view rule, whole-part frames, time-separated calibration) | 16/20 | **0.30** | 2 chips, 1 lid-not-seated | final method; tuned after seeing v1, so optimistic |

**Target ≤ 0.10 is NOT met on the stand-in data.** Marks 3/3 and lid missing 3/3 are caught; chips are not, because
hand-held phone frames change the camera angle so much that good outlines vary as much as a chip does
(good solidity 0.92–0.99, chips 0.93 / 0.96). On the fixed rig the angle and light never change, so good parts
cluster tightly and the same limits become much sharper — the real 20-part rig test decides.
