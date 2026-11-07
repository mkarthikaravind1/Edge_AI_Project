# M2 on the device — Raspberry Pi 5 (6 Nov 2026)

Device: **Raspberry Pi 5 Model B Rev 1.1**, 4 GB, Bookworm 64-bit, Python 3.11.2, CPU only (no accelerator fitted).
Run with `bash scripts/pi_evidence.sh m2` (menu 3 of `deploy/start_here.sh`). Full laptop-vs-Pi table: `comparison.md`.

## Fair benchmark (batch 1, 4 threads, 320 px, **20 warm-up + 200 timed runs** each) — `benchmark_pi_*.json`

| Model | Size | Inference median | Inference p95 | Total median | FPS (total) | Temp start → end |
|---|---|---|---|---|---|---|
| TFLite **INT8** (shipped) | **3.20 MB** | **16.00 ms** | **17.19 ms** | 18.20 ms | **54.3** | 51.6 → 58.7 °C |
| TFLite full-INT8 (int8 in/out) | 3.23 MB | 6.63 ms | 7.58 ms | 8.61 ms | 114.6 | 57.6 → 60.9 °C |
| TFLite FP32 | 12.13 MB | 23.68 ms | 28.38 ms | 25.88 ms | 37.5 | 63.1 → 72.5 °C |
| ONNX Runtime INT8 | 3.60 MB | 17.38 ms | 22.71 ms | 19.35 ms | 49.4 | 69.7 → 75.2 °C |
| ONNX Runtime FP32 | 12.14 MB | 35.47 ms | 43.43 ms | 37.43 ms | 26.0 | 74.7 → 81.8 °C |

Photo of the run on the monitor: `pi_m2_benchmark_photo.jpg`.
Honest note: no cooler was fitted; the Pi warmed up across the runs (last run up to 81.8 °C, below the 85 °C
throttle point). The FP32 ONNX run came last and warmest, so it may be slightly slower than on a cool Pi.

## Convert and run live
`live_int8_pi.mp4`: the TFLite INT8 model running live on the Pi with the USB webcam for 30 s (final 15.6 FPS,
camera-limited).

## Accuracy check on the Pi — `accuracy_compare_pi.json`
Same 18 real test images, run on the Pi's own runtimes: TFLite INT8 and ONNX INT8 both **mAP@0.5 1.000,
mAP@0.5:0.95 1.000** (precision 0.84 / recall 1.00 at conf 0.25). FP32 vs INT8 on the real validation set
(laptop, same models): `comparison.md` — TFLite INT8 drop **0.0007**, ONNX INT8 drop 0.0244 (target ≤ 0.03).

## CPU vs accelerator
No accelerator (Coral / Hailo / GPU delegate) is fitted on this Pi, so the comparison is **CPU FP32 vs CPU INT8**:
INT8 is **1.5× (TFLite) to 2× (ONNX) faster and 3.8× smaller**. Software stack: `docs/stack.png`.

## Own target vs result (`docs/TARGETS.md`, written before training)
| Target | Pi 5 result | Met? |
|---|---|---|
| INT8 mAP@0.5 drop ≤ 0.03 | 0.0007 (TFLite INT8) | ✅ |
| INT8 size ≤ 4 MB | 3.20 MB | ✅ |
| Pi 5 inference median ≤ 60 ms | 16.0 ms | ✅ |
| Live FPS ≥ 12 on Pi 5 | 15.5 (camera-limited) | ✅ |

Trade-off in simple words: INT8 stores the weights as 8-bit numbers instead of 32-bit, so the file is about 4×
smaller and the Pi's CPU does the maths faster, while the boxes stay just as good on my test images. The price is
a calibration step and a tiny accuracy risk on unusual images, which the accuracy check above measures.
