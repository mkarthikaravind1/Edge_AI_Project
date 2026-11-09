# M2 — Optimize: evidence index

Every M2 checklist item, the number that proves it, and the exact files. Files stay flat in this folder because the
scripts write them here; this page is the map.

**Where it ran:** ✅ Pi = measured on the Raspberry Pi 5 (CPU only, no accelerator) · 💻 = measured on the laptop.
Device run notes: [PI_RUN.md](PI_RUN.md) · full laptop-vs-Pi table: [comparison.md](comparison.md).

| # | Criterion | Result | Evidence | Where |
|---|---|---|---|---|
| 2.1 | Export to ONNX | `best.pt` (6.2 MB) → ONNX FP32 12.1 MB, opset 13, batch 1, 320×320 | [export.json](export.json), model [best.onnx](../../models/best.onnx) | 💻 |
| 2.2 | INT8 + convert and run live | TFLite INT8 **3.2 MB**, ONNX INT8 3.6 MB (200 calibration images from train only); TFLite INT8 live on the Pi at 15.6 FPS (camera-limited) | [live_int8_pi.mp4](live_int8_pi.mp4) (30 s), [export.json](export.json) · laptop: [live_overlay_laptop_tflite_int8.png](live_overlay_laptop_tflite_int8.png), [live_overlay_laptop_onnx_int8.png](live_overlay_laptop_onnx_int8.png) | ✅ Pi |
| 2.3 | Accuracy check | Real val mAP@0.5 drop vs FP32: TFLite INT8 **0.0007**, ONNX INT8 0.0244 (target ≤ 0.03); on the Pi runtimes both INT8 models score mAP@0.5 1.000 on the 18 real test images | [accuracy_compare_pi.json](accuracy_compare_pi.json), [accuracy_compare.json](accuracy_compare.json), [comparison.md](comparison.md) | ✅ Pi + 💻 |
| 2.4 | Fair benchmark | Batch 1, 4 threads, 320 px, 20 warm-up + 200 timed runs; Pi TFLite INT8 inference median **16.0 ms**, p95 17.2 ms, **54.3 FPS** | Pi: [tflite_int8](benchmark_pi_tflite_int8.json), [tflite_int8_full](benchmark_pi_tflite_int8_full.json), [tflite_fp32](benchmark_pi_tflite_fp32.json), [onnx_int8](benchmark_pi_onnx_int8.json), [onnx_fp32](benchmark_pi_onnx_fp32.json), [pi_m2_benchmark_photo.jpg](pi_m2_benchmark_photo.jpg) · laptop: [pytorch_fp32](benchmark_laptop_pytorch_fp32.json), [onnx_fp32](benchmark_laptop_onnx_fp32.json), [onnx_int8](benchmark_laptop_onnx_int8.json), [tflite_fp32](benchmark_laptop_tflite_fp32.json), [tflite_fp16](benchmark_laptop_tflite_fp16.json), [tflite_int8](benchmark_laptop_tflite_int8.json), [tflite_int8_full](benchmark_laptop_tflite_int8_full.json) | ✅ Pi |
| 2.5 | CPU vs accelerator + stack | No accelerator fitted → CPU FP32 vs CPU INT8: INT8 **1.5× (TFLite) – 2× (ONNX) faster, 3.8× smaller** | [comparison.md](comparison.md), [comparison.json](comparison.json), stack diagram [stack.png](../../docs/stack.png) | ✅ Pi |
| 2.6 | Own target & trade-off | All 4 targets (set before training) met on the Pi 5: drop 0.0007 ≤ 0.03 · 3.2 MB ≤ 4 MB · 16.0 ms ≤ 60 ms · 15.5 FPS ≥ 12 | [TARGETS](../../docs/TARGETS.md), [OPTIMISATION](../../docs/OPTIMISATION.md), [PI_RUN.md § target](PI_RUN.md#own-target-vs-result-docstargetsmd-written-before-training) | ✅ Pi |

## Code that produced it
| # | Script |
|---|---|
| 2.1 | [export.py](../../scripts/export.py) |
| 2.2 | [quantize_onnx.py](../../scripts/quantize_onnx.py), [export_colab.ipynb](../../scripts/export_colab.ipynb), [run_live.py](../../scripts/run_live.py) |
| 2.3 | [evaluate.py](../../scripts/evaluate.py) |
| 2.4 | [benchmark_model.py](../../scripts/benchmark_model.py) |
| 2.5 | [compare_backends.py](../../scripts/compare_backends.py), [draw_stack.py](../../scripts/draw_stack.py) |
| 2.6 | backends in [backends.py](../../src/edgevision/detect/backends.py) |

## Honest limits
- No cooler fitted: the Pi warmed up across runs (up to 81.8 °C); the FP32 ONNX run came last and warmest.
- The test set is saturated (1.000 for every backend), so the INT8-vs-FP32 drop is measured on the 36 real val frames.

More: [VIVA_NOTES § M2](../../docs/VIVA_NOTES.md#m2-optimize) · all numbers: [RESULTS § M2](../../docs/RESULTS.md#m2)
