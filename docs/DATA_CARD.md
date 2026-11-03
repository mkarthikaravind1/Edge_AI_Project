# Data card — dataset v1

_Counts are filled from `evidence/M1/split_report.json`, `extract_frames.json`, `augment.json` and `label_check.json` once the video is processed._

## Classes
| id | name | object | source |
|---|---|---|---|
| 0 | enclosure | the printed part, closed (lid slid onto body) | my prints + CAD renders (lid seated −6 mm) |
| 1 | body | Model 1 — enclosure body, open tray with two round holes | my prints + CAD renders |
| 2 | lid | Model 2 — sliding lid plate | my prints + CAD renders |

Why three classes: the closed box looks nothing like the open body or the loose lid, so labelling it as
"body + lid" would be ambiguous. This also matches the brief: printed part + Model 1 + Model 2.

## Sources
| Source | How produced | Used in |
|---|---|---|
| Real frames | `extract_frames.py` from my videos: sampled at ~4 fps, blur filter (Laplacian var < 60 dropped), near-duplicate filter (pHash ≤ 6 dropped) | train / val / test |
| Synthetic renders | `render_cad.py` from my STL: random pose, distance, light, PLA colour, background, distractors; boxes from the pixel mask | train / val only |
| Augmented | `augment.py` (flip, affine, brightness/contrast, HSV, blur, noise, JPEG) on **train only, after splitting** | train only |

## Counts
| Split | Real | Synthetic | Augmented | enclosure | body | lid |
|---|---|---|---|---|---|---|
| train | | | | | | |
| val | | | – | | | |
| test | | 0 | – | | | |

## Capture conditions
| Clip | Camera | Resolution | Length | Background | Lighting | Content |
|---|---|---|---|---|---|---|
| clip1.mp4 | phone (WhatsApp-compressed) | 480×854 portrait, 29.8 fps | 73.8 s | wooden desk | indoor room light | closed box, open body, loose lid, hand-held and on desk |

Frame extraction (clip1): 314 sampled at ~4 fps → 72 dropped as blurry (Laplacian var < 60, ≈ bottom 25 % of this video)
→ 25 dropped as near-duplicates (pHash ≤ 6) → **217 kept**. Evidence: `evidence/M1/extract_frames.json`.

## Labelling rules
1. One box per **visible** part, tight to the outer plastic edge (not the shadow).
2. Closed box (lid on) → **one** `enclosure` box around the whole box. Open tray → `body`. Loose plate → `lid`.
   Lid half slid on → `enclosure` if it covers most of the body, otherwise `body` + `lid`.
3. Label a part if ≥ ~30 % of it is visible; skip it if it is cut off so much that I can't tell body from lid.
4. Edge-on lid (only a thin strip visible) is still labelled `lid`.
5. Hands/fingers are not labelled; a part partly covered by fingers is still labelled (box around the whole part as I judge it).
6. Pre-labels from `autolabel.py` are always reviewed before use; each reviewed frame is logged in
   `data/labelled/reviewed.csv` with **who** reviewed it. Only reviewed frames go to `split.py`.

## Review log
| Pass | Who | What | Result |
|---|---|---|---|
| 1 | Claude (AI assistant), from contact sheets | YOLO-World boxes kept, classes corrected, 3 false boxes deleted (finger, two holes) | 111 / 217 frames accepted; 106 had a missing part → pass 2 (`data/labelled/review_pass1_claude.json`) |
| 2 | helper model, checked by Claude | `train_prelabel.py` on the 111 accepted frames + renders → re-labelled the 106 (168 boxes, 83 lids vs 8 from YOLO-World); 7 class/box fixes | 99 accepted; 7 left for me (part hidden by hand / missed lid) (`review_pass2_claude.json`) |
| final | **me (Karthik)** | every frame checked in `review_labels.py --reviewer karthik` | _pending_ |

## Split
70 / 20 / 10 by **contiguous time blocks** per video, 1 s guard gap at block boundaries, synthetic by render-seed group;
cross-split pHash check. Test = real images only. Details: `evidence/M1/split_report.json`.

## Known gaps
- One clip, one background (wooden desk), one lighting → the test set shares that background. More clips planned.
- Phone video is WhatsApp-compressed (480×854) → lower detail than the Pi camera will give.
- Only 2 physical copies of each part → limited variation in print defects and colour.
- Synthetic renders are flat-shaded (no texture/layer lines) → the domain gap is why real frames dominate val/test.
- _Add any lighting/background that is missing after reviewing errors._
