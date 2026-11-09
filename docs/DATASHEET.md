# Datasheet — Edge Inspection Station (Karthik Aravind M, S10)

## 1. Product
Edge vision station that detects and inspects my IDRP 3D-printed enclosure (white PLA). Three object classes:
**enclosure** (closed printed part, ≈ 50 × 25.2 × 12.5 mm), **Model 1 = body** (open tray, 50 × 25.2 × 10.7 mm, two round holes)
and **Model 2 = lid** (sliding plate, 50 × 25.2 × 4 mm). Models split from my CAD file
`cad/enclosure_full.stl` → `cad/model1_body.stl`, `cad/model2_lid.stl`.

## 2. Hardware

| Item | Laptop (development) | Edge device |
|---|---|---|
| Device | laptop | **Raspberry Pi 5 Model B Rev 1.1** |
| CPU | Intel Core Ultra 5 225H (14 cores) | Arm Cortex-A76 ×4 (BCM2712) |
| RAM | 16 GB | 4 GB |
| Accelerator | none | none (CPU only) |
| OS | Windows 11, Python 3.12 | Raspberry Pi OS (Legacy) 64-bit, Bookworm, Python 3.11.2 |
| Camera | built-in webcam | USB webcam SunplusIT ZQ-1080RL, 640×480 MJPG |
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
| mAP@0.5 (real test set) | ≥ 0.85 | 0.995 (YOLOv8n-320, PyTorch FP32) | 1.000 (TFLite INT8 on the Pi runtime, 18 images) |
| Pipeline FPS | ≥ 12 (Pi 5) | 68.6 (uncapped, video source) | 15.55 (USB webcam, camera-limited) |
| Frame latency median / p95 | ≤ 120 ms | 12.4 / 20.7 ms | 19.3 / 23.1 ms |
| Inference median (TFLite INT8) | ≤ 60 ms (Pi 5) | 9.0 ms | 16.0 ms |
| Frame→actuator p95 | ≤ 600 ms | 8.8 ms | _pending (M3 on the Pi)_ |
| Model size INT8 | ≤ 4 MB | 3.2 MB (TFLite INT8, shipped) | 3.2 MB (same file) |
| SoC temperature under load | < 80 °C | n/a | 60.7 °C mean / 63.7 °C peak (live pipeline, no cooler) |

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
