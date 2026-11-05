# Datasheet — Edge Inspection Station (Karthik Aravind M, S10)

## 1. Product
Edge vision station that detects and inspects my IDRP 3D-printed enclosure (white PLA). Three object classes:
**enclosure** (closed printed part, ≈ 50 × 25.2 × 12.5 mm), **Model 1 = body** (open tray, 50 × 25.2 × 10.7 mm, two round holes)
and **Model 2 = lid** (sliding plate, 50 × 25.2 × 4 mm). Models split from my CAD file
`cad/enclosure_full.stl` → `cad/model1_body.stl`, `cad/model2_lid.stl`.

## 2. Hardware

| Item | Laptop (development) | Edge device |
|---|---|---|
| Device | _fill from `evidence/M1/first_frame.json` → host_ | Raspberry Pi _(4 / 5 — fill)_ |
| CPU | _auto-recorded in every evidence json_ | _fill_ |
| RAM | | |
| Accelerator | none | none / Coral / Hailo _(fill)_ |
| OS | Windows 11 | Raspberry Pi OS (Legacy) 64-bit, Bookworm |
| Camera | built-in webcam | USB webcam (mentor's), 640×480 MJPG _(model — fill)_ |
| Actuator | console (fake) | relay / LED on GPIO17 (pin 11) |
| Vibration sensor | CSV replay (fake) | MPU6050 on I²C-1 (0x68) |
| PLC | in-memory fake | OpenPLC runtime, Modbus TCP :502 |

## 3. Software stack
Camera (Picamera2 / OpenCV) → OpenCV pre-processing → runtime (PyTorch / ONNX Runtime / TFLite INT8) → decision engine
→ actuator (gpiozero) + MQTT (Mosquitto, TLS) + Modbus TCP → FastAPI dashboard. Packaged in Docker, started by systemd.
See [ARCHITECTURE.md](ARCHITECTURE.md).

## 4. Performance (measured — see [RESULTS.md](RESULTS.md))

| Metric | Target | Laptop | Pi |
|---|---|---|---|
| mAP@0.5 (real test set) | ≥ 0.85 | 0.995 (YOLOv8n-320, PyTorch FP32) | — |
| Pipeline FPS | ≥ 6 (Pi 4) | 68.6 (uncapped, video source) | |
| Frame latency median / p95 | ≤ 120 ms | 12.4 / 20.7 ms | |
| Frame→actuator p95 | ≤ 600 ms | | |
| Model size INT8 | ≤ 4 MB | 3.2 MB (TFLite INT8, shipped) | |
| SoC temperature under load | < 80 °C | n/a | |

## 5. Headline metric
**Parts classified correctly out of all operator-checked parts** (shown live as e.g. "19/20 correct"), with the
**false-pass rate** (defective parts judged PASS ÷ defective parts) right beside it.

How it is measured, live:
1. The station turns frames into parts (`decide/parts.py`): a part starts when it appears, ends after 5 empty frames;
   result = FAIL if ≥ 3 of 5 frames were FAIL while it was in view, else PASS.
2. The operator marks each part *good* / *defective* on the dashboard (or `POST /api/parts/{id}/truth`).
3. `dashboard/kpis.py`: correct = PASS∧good + FAIL∧defective; headline = correct / marked; false-pass rate =
   PASS∧defective / defective. Shown on the dashboard, in `GET /api/kpis`, and offline in `evidence/M5/passfail.json`
   for the fixed 20-part set.

| | Target | Laptop stand-in | Pi rig |
|---|---|---|---|
| Correct / 20 (fixed set) | ≥ 18/20 | 16/20 (with simulated defects) | _pending_ |
| False-pass rate | ≤ 10 % | 30 % | _pending_ |

The other two dashboard KPIs: **throughput** (parts per minute over the last 5 min), **yield** (% PASS), and
**median latency** (part's first frame → reject output).

## 6. Interfaces
- Dashboard: `http://<device>:8000` (REST `/api/*`, WebSocket `/ws`, MJPEG `/video.mjpg`; works offline)
- MQTT (TLS 8883): `edge/<device_id>/detection`, `edge/<device_id>/motor/score`, `edge/<device_id>/status`
- Modbus TCP: coil 0 (%QX0.0) = reject/stop, holding register 0 = part count
