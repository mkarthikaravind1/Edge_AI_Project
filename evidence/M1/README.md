# M1 — Detect: evidence index

Every M1 checklist item, the number that proves it, and the exact files. Files stay flat in this folder because the
scripts write them here; this page is the map.

**Where it ran:** ✅ Pi = measured on the Raspberry Pi 5 · 💻 = measured on the laptop · every json records its host.
Device run notes: [PI_RUN.md](PI_RUN.md) (Raspberry Pi 5, 4 GB, Bookworm, USB webcam 640×480, 6 Nov 2026).

| # | Criterion | Result | Evidence | Where |
|---|---|---|---|---|
| 1.1 | Camera & repo | First 640×480 frame from the USB webcam through the HAL | [first_frame_pi.png](first_frame_pi.png), [first_frame_pi.json](first_frame_pi.json), [pi_setup_check_photo.jpg](pi_setup_check_photo.jpg) · laptop: [first_frame.json](first_frame.json) | ✅ Pi |
| 1.2 | OpenCV pipeline (live overlay) | Boxes + class + confidence + per-class count + FPS live; body 0.95, lid 0.96 on the Pi | [live_overlay_pi.mp4](live_overlay_pi.mp4) (30 s), [live_overlay_pi.png](live_overlay_pi.png), [pi_m1_results_photo.jpg](pi_m1_results_photo.jpg) · laptop: [live_overlay_laptop.png](live_overlay_laptop.png) | ✅ Pi |
| 1.3 | Baseline speed | **15.55 FPS** over 60 s (camera-limited); frame latency median **19.3 ms**, p95 23.1 ms; CPU 27.7 % mean; 60.7 °C mean | [baseline_pi.json](baseline_pi.json), [baseline_pi_samples.csv](baseline_pi_samples.csv) · laptop: [baseline_laptop.json](baseline_laptop.json), [baseline_laptop_samples.csv](baseline_laptop_samples.csv), COCO yolov8n reference [baseline_laptop_coco_yolov8n.json](baseline_laptop_coco_yolov8n.json) | ✅ Pi |
| 1.4 | Dataset v1 | 74 s video → 314 sampled → **217 frames kept** (72 blurry, 25 duplicates dropped); + CAD renders; 3 classes enclosure / body / lid; two-pass auto-label, every frame reviewed by hand | [extract_frames.json](extract_frames.json), [autolabel_world.json](autolabel_world.json), [prelabel_model.json](prelabel_model.json), [autolabel_model.json](autolabel_model.json), [label_check.json](label_check.json), [label_check_real.json](label_check_real.json), [label_check_synthetic.json](label_check_synthetic.json), review log [reviewed.csv](../../data/labelled/reviewed.csv) · [DATA_CARD](../../docs/DATA_CARD.md) | 💻 |
| 1.5 | Correct split | Time-block split (20 blocks, 0.5 s gap), pHash leakage check; train 126 real + 350 synthetic, val 36 real + 100 synthetic, **test 18 real only**; augmentation (×2) on train only, after the split | [split_report.json](split_report.json), [augment.json](augment.json), [data.yaml](../../data/splits/data.yaml) | 💻 |
| 1.6 | Train & run detector | YOLOv8n @ 320, real test **mAP@0.5 0.995**, mAP@0.5:0.95 0.995, P 0.979, R 1.000 (real val 0.991 / 0.951); all 4 targets met; 10 wrong detections analysed | [train_eval.json](train_eval.json), [eval_val_real.json](eval_val_real.json), [train_320_results.png](train_320_results.png), [train_320_results.csv](train_320_results.csv), [test_320_confusion_matrix.png](test_320_confusion_matrix.png), [test_320_confusion_matrix_normalized.png](test_320_confusion_matrix_normalized.png), 640 comparison: [train_640_results.png](train_640_results.png), [test_640_confusion_matrix.png](test_640_confusion_matrix.png) · [wrong_detections/](wrong_detections/wrong_detections.md) · targets set before training: [TARGETS](../../docs/TARGETS.md) | 💻 train, ✅ runs on Pi (1.2) |

## Code that produced it
| # | Script |
|---|---|
| 1.1 | [capture_frame.py](../../scripts/capture_frame.py) |
| 1.2 | [run_live.py](../../scripts/run_live.py), overlay in [overlay.py](../../src/edgevision/pipeline/overlay.py) |
| 1.3 | [benchmark_pipeline.py](../../scripts/benchmark_pipeline.py) |
| 1.4 | [extract_frames.py](../../scripts/extract_frames.py), [render_cad.py](../../scripts/render_cad.py), [autolabel.py](../../scripts/autolabel.py), [train_prelabel.py](../../scripts/train_prelabel.py), [review_labels.py](../../scripts/review_labels.py), [check_labels.py](../../scripts/check_labels.py) |
| 1.5 | [split.py](../../scripts/split.py), [augment.py](../../scripts/augment.py) |
| 1.6 | [train_colab.ipynb](../../scripts/train_colab.ipynb), [evaluate.py](../../scripts/evaluate.py), [wrong_detections.py](../../scripts/wrong_detections.py) |

## Honest limits
- One video, one desk, one light: the test score means "same scene", not new scenes.
- 18 test images (3 body boxes): one extra mistake moves precision by about 5 points.
- On the Pi's webcam and new background the model still finds body and lid but adds false boxes (see 1.2 photo).

More: [VIVA_NOTES § M1](../../docs/VIVA_NOTES.md#m1-detect) · all numbers: [RESULTS § M1](../../docs/RESULTS.md#m1)
