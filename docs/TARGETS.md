# My targets (written BEFORE training, 3 Nov 2026)

These are fixed before any model is trained, so the result can be judged honestly against them.
Machine-readable copy: [`targets.json`](targets.json) (read by the Colab notebook and the reports).

## Accuracy (M1, on the held-out **real** test set, IoU 0.5)

| Metric | Target | Why this number |
|---|---|---|
| mAP@0.5 | **≥ 0.85** | Two large, rigid, single-colour parts on a plain background: a nano model normally reaches 0.85–0.95. |
| mAP@0.5:0.95 | **≥ 0.60** | Boxes must be tight, but the thin lid makes high-IoU boxes harder. |
| Precision | **≥ 0.85** | A false "part present" fires the actuator for nothing. |
| Recall | **≥ 0.85** | A missed part goes uninspected. |

## Optimisation (M2)

| Metric | Target | Why |
|---|---|---|
| INT8 mAP@0.5 drop vs FP32 | **≤ 0.03** | Typical INT8 loss with a good calibration set is 1–3 points. |
| INT8 model size | **≤ 4 MB** | YOLOv8n FP32 ≈ 12 MB; INT8 ≈ ¼ of that. |
| Inference latency on Pi CPU (INT8, 320, batch 1), median | **≤ 120 ms** (Pi 4) / **≤ 60 ms** (Pi 5) | Gives ≥ 8 / ≥ 15 inferences per second. |
| Live pipeline FPS on Pi | **≥ 6 FPS** (Pi 4) / **≥ 12 FPS** (Pi 5) | Enough for a part that stays in view ≥ 1 s (N-of-M = 3-of-5 needs ~0.5 s at 6 FPS). |

## System (M3–M5)

| Metric | Target | Why |
|---|---|---|
| Frame → actuator latency p95 | **≤ 600 ms** | 3-of-5 debounce at 6 FPS ≈ 0.5 s + inference. |
| False-pass rate (defective part passed) | **≤ 10 %** (≤ 1 of 10) | A false pass is the costly error. |
| Motor false alarms over 5 normal runs | **≤ 1** | Threshold = 99.5th percentile of normal scores. |
| Headline metric | **≥ 18 / 20** parts classified correctly | Shown live on the dashboard. |

Final numbers vs these targets are in [RESULTS.md](RESULTS.md).
