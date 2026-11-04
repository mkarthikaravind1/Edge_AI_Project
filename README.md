# Edge Inspection — Edge AI & Embedded Vision Systems (individual assessment)

**Karthik Aravind M (S10)** · Edge visual-inspection system for my IDRP 3D-printed enclosure,
running on a Raspberry Pi with a live dashboard.

Objects (classes): **enclosure** (my closed printed part), **body** = Model 1, **lid** = Model 2 — both models split from `cad/enclosure_full.stl`.

## Quick start (laptop)

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate          # Windows  (Pi/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pip install -e .
pytest -q
python scripts/capture_frame.py
python scripts/run_live.py
```

`EDGE_TARGET=laptop` (default) uses `config/laptop.yaml`; `EDGE_TARGET=pi` uses `config/pi.yaml`.

## Layout

| Path | What |
|---|---|
| `src/edgevision/hal/` | Camera, actuator, IMU, PLC interfaces + laptop fakes + Pi implementations |
| `src/edgevision/detect/` | Detector interface; Ultralytics (FP32), ONNX Runtime, TFLite (INT8) backends |
| `src/edgevision/pipeline/` | Single/two-stream runners, overlay, FPS/latency meters |
| `src/edgevision/decide/` | N-of-M debounce, cooldown, camera-loss safe state |
| `src/edgevision/monitor/` | IMU features, anomaly model (normal-only) |
| `scripts/` | capture, extract, render, autolabel, review_labels, split, augment, train (Colab), benchmark, report |
| `cad/` | my CAD: full enclosure, Model 1 (body), Model 2 (lid) |
| `docs/` | datasheet, data card, targets, Pi checklist, viva notes, results |
| `evidence/M1..M5/` | every measured number (json/csv/png) |

## Milestone status

| Milestone | Status |
|---|---|
| M1 Detect | laptop done (mAP@0.5 0.995 on real test); Pi runs pending |
| M2 Optimize | laptop done: TFLite INT8 3.2 MB, mAP50 drop 0.001 (ONNX INT8 3.6 MB, drop 0.024); Pi benchmarks pending |
| M3 Decide and Act | laptop done: debounce demo, safe state 1.06 s, 2 streams x 30 FPS, e2e p95 8.8 ms; Docker + Pi runs pending |
| M4 Monitor and Connect | laptop done: MQTT TLS 6/6, topics, PLC link, OTA rollback, drift, anomaly (synthetic IMU); real IMU + OpenPLC on Pi pending |
| M5 Complete System | – |

Results: [docs/RESULTS.md](docs/RESULTS.md) · Device checklist: [docs/PI_CHECKLIST.md](docs/PI_CHECKLIST.md)
