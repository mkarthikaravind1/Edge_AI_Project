# M2 Optimise — what I did and what it cost

Full generated table: [`evidence/M2/comparison.md`](../evidence/M2/comparison.md) · accuracy: `evidence/M2/accuracy_compare.json` ·
speed: `evidence/M2/benchmark_<host>_<backend>.json` · export details: `evidence/M2/export.json` · stack: [ARCHITECTURE.md](ARCHITECTURE.md)

## Pipeline
`best.pt` (PyTorch, FP16 weights on disk) → **ONNX FP32** (`scripts/export.py`, opset 13, batch 1, 320×320)
→ **ONNX INT8** (`scripts/quantize_onnx.py`, ONNX Runtime static quantisation)
→ **TFLite INT8** (`scripts/export_colab.ipynb`; Ultralytics only exports TFLite on Linux/macOS).

INT8 calibration: 200 images from the **train split only** (126 real frames + 74 renders, no augmented copies),
pre-processed exactly like the live pipeline. Val/test are never shown to the quantiser.

## Laptop results (Intel Core Ultra 5 225H, 4 threads, batch 1, 200 timed runs)

| backend | size MB | inference median / p95 ms | real-val mAP@0.5 | real-val mAP@0.5:0.95 |
|---|---|---|---|---|
| PyTorch FP32 | 6.2 | 9.7 / 11.3 | 0.970 | 0.922 |
| ONNX FP32 | 12.1 | 9.3 / 12.5 | 0.975 | 0.934 |
| **ONNX INT8** | **3.6** | **5.2 / 7.3** | **0.950** | **0.886** |
| TFLite INT8 | _after Colab export_ | | | |

The real test split (18 images) scores 1.000 for every backend, so it cannot show differences; the 36 real val frames
are used for the comparison. **These are laptop numbers; the Pi numbers go in the same table after the Pi run.**

## Target vs achieved

| target (written 3 Nov, before training) | achieved | met? |
|---|---|---|
| INT8 mAP@0.5 drop ≤ 0.03 | 0.019 vs PyTorch FP32 (0.024 vs ONNX FP32) | ✅ |
| INT8 model ≤ 4 MB | 3.6 MB | ✅ |
| Pi INT8 median inference ≤ 120 ms (Pi 4) / 60 ms (Pi 5) | _pending Pi run_ | ⏳ |
| Pi pipeline ≥ 6 FPS (Pi 4) / 12 FPS (Pi 5) | _pending Pi run_ | ⏳ |

## Trade-off in plain words
INT8 stores every weight in 1 byte instead of 4, and does the maths in small integers, so the model is **3.4× smaller**
and **1.8× faster** on my laptop CPU (and usually 2–3× on an Arm CPU, which has fast int8 instructions). The price is
rounding: a value like 0.4371 becomes the nearest of 256 steps. Finding *whether* a part is there barely changes
(mAP@0.5 drops 0.02), but drawing a *tight* box suffers more (mAP@0.5:0.95 drops 0.05), and the class that suffers most
is `enclosure` (AP@0.5 0.93 → 0.86), the class already confused with the lid seen from above. For my station that is the
right trade: the decision only needs "is a part there, and which one" at ≥ 0.60 confidence, and N-of-M debounce absorbs a
single wrong frame, while the Pi needs the speed to reach the FPS target. If the enclosure/lid confusion shows up on the
rig, the fix is a better camera angle and more data, not going back to FP32.

## Why some numbers look odd
- **ONNX FP32 file is larger than best.pt** (12.1 vs 6.2 MB): best.pt stores FP16 weights; ONNX FP32 stores 4 bytes each.
- **ONNX FP32 is a hair more accurate than PyTorch**: same weights, but my ONNX path pads the image to a full 320×320
  square while Ultralytics trims the padding, so the network sees slightly different pixels.
- **My mAP differs from Ultralytics' printout** (0.97 vs 0.99 on val): different matching/interpolation code. That is why
  every backend here is scored by the **same** `scripts/evaluate.py`.
