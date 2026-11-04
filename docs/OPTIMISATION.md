# M2 Optimise — what I did and what it cost

Full generated table: [`evidence/M2/comparison.md`](../evidence/M2/comparison.md) · accuracy: `evidence/M2/accuracy_compare.json` ·
speed: `evidence/M2/benchmark_<host>_<backend>.json` · export details: `evidence/M2/export.json` · stack: [ARCHITECTURE.md](ARCHITECTURE.md)

## Pipeline
`best.pt` (PyTorch, FP16 weights on disk) → **ONNX FP32** (`scripts/export.py`, opset 13, batch 1, 320×320)
→ **ONNX INT8** (`scripts/quantize_onnx.py`, ONNX Runtime static quantisation)
→ **TFLite FP32 / FP16 / INT8 / full-integer INT8** (`scripts/export_colab.ipynb`, run in Colab on Linux in a pinned
Python 3.12 env: TF 2.19, onnx2tf 1.27.10; Ultralytics only exports TFLite on Linux/macOS).

INT8 calibration: 200 images from the **train split only** (126 real frames + 74 renders, no augmented copies),
pre-processed exactly like the live pipeline. Val/test are never shown to the quantiser.

## Laptop results (Intel Core Ultra 5 225H, 4 threads, batch 1, 200 timed runs)

| backend | size MB | inference median / p95 ms | detect() median ms | real-val mAP@0.5 | real-val mAP@0.5:0.95 |
|---|---|---|---|---|---|
| PyTorch FP32 | 6.2 | 9.7 / 11.3 | 11.1 | 0.970 | 0.922 |
| ONNX FP32 | 12.1 | 9.3 / 12.5 | 10.9 | 0.975 | 0.934 |
| ONNX INT8 (mine, ORT static) | 3.6 | 5.2 / 7.3 | 6.6 | 0.950 | 0.886 |
| TFLite FP32 | 12.1 | 12.7 / 14.8 | 15.9 | 0.975 | 0.934 |
| TFLite FP16 | 6.1 | 12.7 / 14.4 | 15.4 | 0.975 | 0.934 |
| **TFLite INT8** (float in/out) | **3.2** | **9.0 / 10.8** | **11.5** | **0.974** | **0.929** |
| TFLite INT8 full-integer (int8 in/out) | 3.2 | 7.4 / 10.0 | 8.8 | 0.975 | 0.877 |

The real test split (18 images) scores 1.000 mAP@0.5 for every backend, so it cannot separate them; the 36 real val
frames are used. **These are laptop (x86) numbers. TFLite is built for Arm, so on x86 it trails ONNX Runtime; the Pi
benchmark decides which runtime ships.** Full table: `evidence/M2/comparison.md`.

## Target vs achieved

INT8 is compared with the FP32 model **of the same runtime** (same pre/post-processing, so the only change is quantisation).

| target (written 3 Nov, before training) | ONNX INT8 | TFLite INT8 | TFLite INT8 full | met? |
|---|---|---|---|---|
| mAP@0.5 drop ≤ 0.03 | 0.024 | **0.001** | 0.000 | ✅ all |
| model ≤ 4 MB | 3.6 | **3.2** | 3.2 | ✅ all |
| Pi median inference ≤ 120 ms (Pi 4) / 60 ms (Pi 5) | _pending Pi_ | _pending Pi_ | _pending Pi_ | ⏳ |
| Pi pipeline ≥ 6 FPS (Pi 4) / 12 FPS (Pi 5) | | _pending Pi_ | | ⏳ |

**Shipped on the Pi (`config/pi.yaml`): TFLite INT8** — smallest, almost no accuracy loss, and TFLite's XNNPACK int8
kernels are made for Arm. Full-integer INT8 is kept for a Coral Edge TPU, which needs int8 input/output.

## Trade-off in plain words
INT8 stores every weight in 1 byte instead of 4 and does the maths in small integers: the model is **3.8× smaller**
(12.1 → 3.2 MB) and, on an Arm CPU, typically 2–3× faster. The price is rounding each value to one of 256 steps.
How much that costs depends on *where* you round:
- **TFLite INT8** keeps the input and the final box outputs in float → mAP@0.5 drops 0.001, tight boxes drop 0.005.
- **Full-integer INT8** also rounds the *output*: box coordinates snap to steps of ≈ 2.4 px (scale 0.0074 × 320), so
  "is it there" is unchanged (0.975) but tight boxes fall from 0.934 to 0.877.
- **My ONNX INT8** used simple MinMax calibration and more int8 layers: 0.024 lower mAP@0.5, and the hardest class,
  `enclosure` (confused with the lid seen from above), lost most (AP@0.5 0.93 → 0.86).

For this station the decision only needs "which part is there" at ≥ 0.60 confidence with N-of-M debounce, so the 2.4 px
box rounding does not matter, but losing class accuracy would. That is why TFLite INT8 is the choice: almost all of
the size gain, almost none of the accuracy loss.

## Engineering fix found while benchmarking
Full-integer INT8 first measured 15.5 ms per detect() but only 8.4 ms inside the model: my code made several float
passes (convert, divide, round, clip) over all 307 200 input values to turn them into int8. With input scale exactly
1/255 that is just `pixel − 128` in integer maths; after the change detect() takes 8.8 ms with identical accuracy (`TfliteDetector.detect`).

## Why some numbers look odd
- **ONNX FP32 file is larger than best.pt** (12.1 vs 6.2 MB): best.pt stores FP16 weights; ONNX FP32 stores 4 bytes each.
- **ONNX FP32 is a hair more accurate than PyTorch**: same weights, but my ONNX path pads the image to a full 320×320
  square while Ultralytics trims the padding, so the network sees slightly different pixels.
- **My mAP differs from Ultralytics' printout** (0.97 vs 0.99 on val): different matching/interpolation code. That is why
  every backend here is scored by the **same** `scripts/evaluate.py`.
