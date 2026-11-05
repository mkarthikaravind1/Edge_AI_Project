# Inspection rig (M5.1)

Goal: every part is photographed from **the same place, angle and light**, so "good" always looks the same and any
difference is a defect. Everything below is cheap or already on the desk.

```
          USB webcam on a fixed arm
               \   ~30-45 deg down, 20-25 cm from the part
                \
   desk lamp ->  \        part sits in the stop, always the same way round
   (diffused)     \   ________
                   \ |  part  |<- L-shaped stop (card / 3D-printed corner) taped to the base
     --------------------------------------------  matte, plain base (grey/black card, NOT the wood grain)
```

## Build
1. **Base:** a sheet of matte grey or black card taped flat. A plain base gives a clean outline (white PLA on dark
   card) and removes the wood grain that caused false detections in M1.
2. **Stop:** tape an L-shaped corner (card or a quick 3D print) so every part goes in the same position and orientation:
   lid face up, slot towards the camera.
3. **Camera:** fix it to something that cannot move (phone stand, small tripod, a clamp on a ruler, or a 3D-printed arm).
   Angle ~30–45° so the side wall is visible (this is what separates a closed box from a loose lid — M1 wrong
   detection #7). Distance so the part fills ~40–60 % of the frame width with margin on all sides (fully in view).
4. **Light:** one desk lamp with a sheet of paper as diffuser, from the side opposite the camera, plus ceiling light.
   Close the curtains or always shoot at the same time of day. Lock the camera's exposure if it allows.
5. **Mark the positions** of camera, lamp and stop with tape so the rig can be rebuilt identically.

Photograph the finished rig for the evidence: `evidence/M5/rig_photo.jpg` (and one frame from the station camera:
`EDGE_TARGET=pi python scripts/capture_frame.py --name rig_view`).

## Image set (covers every defect type)
| Folder | Shots | How |
|---|---|---|
| `data/rig/calib_good/` | ~15 | good parts (both prints), put in the stop, take out, put back: small natural variation |
| `data/rig/test/good/` | 10 | good parts, **different placements from calibration** |
| `data/rig/test/defective/` | 10 | ≥ 2 each: mark (`1`), chipped corner (`2`), lid missing (`3`), lid not seated (`4`) |

`EDGE_TARGET=pi python scripts/capture_rig.py` → press `c` / `g` / `d` (and `1–4` to set the defect) for each shot.
Then:
```bash
python scripts/calibrate_inspection.py --dir data/rig/calib_good
python scripts/passfail_test.py --dir data/rig/test          # -> evidence/M5/passfail.json, passfail_confusion.png
```
