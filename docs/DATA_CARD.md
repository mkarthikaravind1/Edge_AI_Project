# Data card — dataset v1

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
| train | 126 | 350 | 252 (2 per real frame) | 244 | 346 | 413 |
| val | 36 | 100 | – | 52 | 81 | 75 |
| test | 18 | 0 | – | 9 | 3 | 9 |

Real frames: 217 extracted → 7 held back in `data/labelled/exclude.txt` (part mostly hidden by my hand; reviewed, kept out of the split) → 30 dropped at split
boundaries → 180 used (126 / 36 / 18 = 70 / 20 / 10 %). Label check: 0 empty, tiny, overlapping or malformed boxes
(`evidence/M1/label_check.json`).

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
| final | me (Karthik), 9 Nov 2026 | `review_labels.py` over all 217 frames, then `review_labels.py --only exclude` on the 7 held-back frames | 1 box corrected (`clip1_000854`: body box too long → tightened); the other labels kept as they are. In the 7 held-back frames, parts mostly hidden by my hand, cut off by the frame edge or heavily blurred are left unlabelled (my decision per frame in `data/labelled/exclude.txt`). The 7 stay out of the split, because the trained model's split was made without them. Log: `data/labelled/reviewed.csv` |

## Split
70 / 20 / 10 by **contiguous time blocks**: the video is cut into 20 blocks (~3.7 s each) and whole blocks go to one split;
frames within 0.5 s of a boundary between different splits are dropped. Of 500 random block assignments, the one kept
has **every class in val and test** and the ratio closest to 70/20/10 (with one video a purely random pick gave a test
set with no `enclosure`). Synthetic by render-seed group (train/val only). Cross-split pHash check: **0 duplicates**.
Test = real images only. Details: `evidence/M1/split_report.json`.

## Known gaps
- One clip, one background (wooden desk), one lighting → the test set shares that background. More clips planned.
- Test set is small (18 images, only 3 body boxes) → mAP on it has a wide error bar; more clips fix this.
- Phone video is WhatsApp-compressed (480×854) → lower detail than the Pi camera will give.
- Only 2 physical copies of each part → limited variation in print defects and colour.
- Synthetic renders are flat-shaded (no texture/layer lines) → the domain gap is why real frames dominate val/test.
