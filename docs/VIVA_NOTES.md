# Viva notes — what to show and what to say

Short "explain it simply" notes per task. Commands assume the venv is active and `EDGE_TARGET` is set.

## Architecture in one breath
Core logic (detect, decide, monitor) never talks to hardware directly. It talks to a **HAL** (hardware abstraction layer):
`Camera`, `Actuator`, `Imu`, `Plc`. On the laptop these are a webcam and fakes; on the Pi they are Picamera2, GPIO, MPU6050
and Modbus. Switching is one setting in `config/<target>.yaml`, chosen by `EDGE_TARGET`.

---

## M1 Detect

**1.1 Camera & repo** — `python scripts/capture_frame.py`
> Opens the camera through the HAL, throws away 10 frames while auto-exposure settles, saves one frame and a json
> that records which machine took it.

**1.2 OpenCV pipeline** — `python scripts/run_live.py`
> Loop: read frame → detector returns boxes → `overlay.draw` paints box, class and confidence, a per-class count and FPS.
> FPS is frames counted over the last 2 seconds.

**1.3 Baseline speed** — `python scripts/benchmark_pipeline.py --seconds 60`
> 20 warm-up frames are not timed (first runs are slow: memory allocation, caches). Then for 60 s I time every frame
> from capture to overlay done, and a background thread samples CPU %, GPU % and temperature every second.
> I report median and p95, not just mean, because a few slow frames hide inside a mean.

**1.4 Dataset v1** — `extract_frames.py`, `render_cad.py`, `autolabel.py`, `check_labels.py`
> - *Blur filter:* the Laplacian highlights edges; a blurry image has few edges so its variance is low → dropped.
> - *Duplicate filter:* a perceptual hash is a 64-bit fingerprint of how the image looks; two frames whose hashes
>   differ in ≤ 6 bits are practically the same picture, so I keep only one.
> - *Synthetic:* I split my STL into body (Model 1) and lid (Model 2) and render them in random pose, light, colour
>   and background. Boxes come from the rendered pixel mask, so they are exact.
> - *Three classes:* the closed box looks different from the open tray and the loose plate, so it gets its own class
>   (`enclosure`) instead of two overlapping boxes.
> - *Auto-label, pass 1:* YOLO-World is a detector you can prompt with text ("closed white plastic box"). It found the
>   parts but mixed up the classes and missed most lids (8 lid boxes on 217 frames), so I corrected ~30 frames by hand.
> - *Auto-label, pass 2:* a helper YOLOv8n trained on those reviewed frames + the CAD renders re-labels the rest; I review
>   every frame in my offline tool (`review_labels.py`), and `reviewed.csv` proves which frames I checked and when.
>   The helper model is not my submitted model, and it only *suggests* boxes, so it cannot leak test data.

**1.5 Correct split** — `python scripts/split.py`
> Neighbouring video frames are near copies. A random split would put one copy in train and its twin in test, and the
> test score would be fake-high (**leakage**). So I cut each video into 20 time blocks and give whole blocks to one
> split, drop frames within 0.5 s of a boundary, and then pHash-check every test image against every train image (0 found).
> With only one video, a random block choice once left `enclosure` out of the test set entirely, so the script tries 500
> block assignments and keeps one where val and test contain every class at 70/20/10.
> Test is real images only, because the device will only ever see real parts.
> Augmentation (flip, small shift/scale/±5° rotation, brightness, blur, light noise) runs on train only, after the split,
> so test never contains an augmented copy of a training image.

**M2 is below M1 in this file.**

**1.6 Train & run** — `scripts/train_colab.ipynb`
> Transfer learning: start from public COCO weights (`yolov8n.pt`), fine-tune on my 3 classes (enclosure, body, lid).
> mAP@0.5 = area under the precision-recall curve, counting a box as correct if it overlaps the truth ≥ 50 %, averaged
> over classes. mAP@0.5:0.95 averages that over stricter overlaps (50 % … 95 %), so it rewards tight boxes.
> Precision = of the boxes I drew, how many were right. Recall = of the real parts, how many I found.
> **My result:** test mAP@0.5 0.995, mAP@0.5:0.95 0.995, P 0.979, R 1.000 (18 real images); real val 0.991 / 0.951.
> I picked 320 over 640: same mAP@0.5, ~4x fewer pixels, so faster on the Pi.
> **Why I don't over-trust it:** one desk, one video, 18 test images, and boxes that a model proposed.
> **One wrong detection to show** (`evidence/M1/wrong_detections/07_CLASS_val_clip1_001862.jpg`): a closed box seen from
> straight above was called "lid", because from the top both are a flat white rectangle and the side walls aren't visible.
> Fix: mount the inspection camera at an angle so the wall height shows. 6 of the 10 errors are slivers of a part cut off at
> the image edge; my labelling rule skips those, so the fix is a decision rule that ignores boxes touching the border.

---

## M2 Optimize

**2.1 Export to ONNX** — `python scripts/export.py --format onnx`
> ONNX is a standard file format for neural networks: any runtime (ONNX Runtime, TensorRT, …) can run it without PyTorch.
> Fixed batch 1 and 320×320 input, opset 13 (needed for per-channel INT8 later).

**2.2 INT8 + run live** — `python scripts/quantize_onnx.py`, `scripts/export_colab.ipynb`, `run_live.py --backend onnx --model models/best_int8.onnx`
> Quantisation maps each float to one of 256 integer steps using a scale and zero-point. To choose the scale, the
> quantiser runs 200 *calibration* images and records the range of every layer's values. They come from the train split
> only, so the model is never tuned on images I later score it on. The last ~30 nodes (box decoding) stay FP32 because
> boxes are sensitive to rounding and that part is cheap anyway.

**2.3 Accuracy check** — `python scripts/evaluate.py`
> One metric implementation for every backend, same real images. Test is saturated (1.000 for all), so I compare on the
> 36 real val frames: FP32 0.970 → INT8 0.950 mAP@0.5 (drop 0.019, target ≤ 0.03).

**2.4 Fair benchmark** — `python scripts/benchmark_model.py --backend onnx_int8`
> Fair = same images, batch 1, same thread count, 20 warm-up runs thrown away (caches, memory allocation), 200 timed runs.
> I report the *median* (typical frame) and *p95* (bad-but-normal frame), plus the pure inference time vs the full
> detect() (pre-processing + NMS), because the live pipeline pays the full cost.

**2.5 CPU vs accelerator + stack** — `evidence/M2/comparison.md`, `docs/stack.png`
> The stack is camera → OpenCV → runtime → delegate → OS → hardware. Without an accelerator my "delegate" is XNNPACK on
> the CPU. The detector is a plug-in, so adding Coral is a config change plus an Edge-TPU-compiled model.

**2.6 Target & trade-off** — `docs/OPTIMISATION.md`
> 3.4× smaller, 1.8× faster on the laptop; "is it there" barely changes, tight boxes and enclosure-vs-lid suffer most.
