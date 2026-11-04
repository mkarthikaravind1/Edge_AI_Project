# Raspberry Pi checklist

Everything that must be **measured on the Pi** is here, with the exact commands and where the result lands.
Laptop numbers never count as device results; every evidence json records `host.device_type`.

---

## 0. One-time setup (fresh Raspberry Pi OS 64-bit, Bookworm)

Flash with Raspberry Pi Imager → set hostname `pi-karthik`, user, Wi-Fi, **enable SSH**. Then on the Pi:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-picamera2 python3-gpiozero python3-smbus2 i2c-tools \
                    libgl1 libglib2.0-0 mosquitto mosquitto-clients
sudo raspi-config nonint do_i2c 0          # enable I2C
sudo raspi-config nonint do_camera 0 2>/dev/null || true   # Bookworm: camera auto-detected
sudo reboot
```

After reboot, check the hardware:

```bash
rpicam-hello --list-cameras                # Pi camera visible?
ls /dev/video*                             # USB webcam visible?
i2cdetect -y 1                             # MPU6050 shows 68
vcgencmd measure_temp
```

Get the code (system site packages so picamera2/gpiozero from apt are visible):

```bash
cd ~ && git clone https://github.com/mkarthikaravind1/Edge_AI_Project.git && cd Edge_AI_Project
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
pip install -r requirements-pi.txt && pip install -e .
export EDGE_TARGET=pi
pytest -q                                  # all tests must pass on the Pi too
```

Docker (needed from M3):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker run --rm hello-world
```

---

## M1 — Detect (on the Pi)

Copy the trained/exported model to the Pi first (commit `models/best.onnx` from the laptop, then `git pull` on the Pi).

| # | Command (on the Pi, venv active, `EDGE_TARGET=pi`) | Result file |
|---|---|---|
| 1.1 | `python scripts/capture_frame.py --name first_frame_pi` | `evidence/M1/first_frame_pi.png/.json` |
| 1.2 | `python scripts/run_live.py --backend onnx --model models/best.onnx --headless --seconds 30 --save evidence/M1/live_overlay_pi.mp4` then grab a screenshot from the video | `evidence/M1/live_overlay_pi.mp4` |
| 1.3 | `python scripts/benchmark_pipeline.py --seconds 60` (with `--backend` from config) | `evidence/M1/baseline_pi.json` + `_samples.csv` |

Fill the Pi column of `docs/DATASHEET.md` from `baseline_pi.json → host`.

## M2 — Optimize (on the Pi)

Models come from git (`git pull`): `models/best.onnx`, `models/best_int8.onnx`, `models/best_fp32.tflite`, `models/best_int8.tflite`, `models/best_int8_full.tflite`.
After all 2.4 runs: `git add evidence/M2 && git commit -m "M2: Pi benchmarks" && git push`, then on the laptop `git pull` and run 2.5.
Close other programs; let the Pi idle 2 minutes first so it starts cool. Run with a fan/heatsink if you have one, and say so.

| # | Command (on the Pi, venv active, `EDGE_TARGET=pi`) | Result file |
|---|---|---|
| 2.4a | `python scripts/benchmark_model.py --backend onnx_fp32 --threads 4` | `evidence/M2/benchmark_pi_onnx_fp32.json` |
| 2.4b | `python scripts/benchmark_model.py --backend onnx_int8 --threads 4` | `evidence/M2/benchmark_pi_onnx_int8.json` |
| 2.4c | `python scripts/benchmark_model.py --backend tflite_int8 --threads 4` | `evidence/M2/benchmark_pi_tflite_int8.json` |
| 2.4d | `python scripts/benchmark_model.py --backend tflite_fp32 --threads 4` (CPU FP32 vs INT8) | `evidence/M2/benchmark_pi_tflite_fp32.json` |
| 2.4e | `python scripts/benchmark_model.py --backend tflite_int8_full --threads 4` | `evidence/M2/benchmark_pi_tflite_int8_full.json` |
| 2.2 | `python scripts/run_live.py --backend tflite --model models/best_int8.tflite --headless --seconds 30 --save evidence/M2/live_int8_pi.mp4` | `evidence/M2/live_int8_pi.mp4` |
| 2.3 | `python scripts/evaluate.py --backends onnx_int8 tflite_int8` (optional: same accuracy on the Pi runtime) | `evidence/M2/accuracy_compare.json` |
| 2.5 | `python scripts/compare_backends.py` (back on the laptop after `git pull`) | `evidence/M2/comparison.md` |

If a Coral/Hailo accelerator is fitted, tell Claude: it needs an Edge-TPU-compiled model and `delegate: libedgetpu.so.1`.

## M3 — Decide and act (on the Pi)
_Added at M3: GPIO wiring table, two-stream run, Docker cold-boot test, end-to-end latency._

## M4 — Monitor and connect (on the Pi)
_Added at M4: MPU6050 wiring table + recorder commands (3 normal + 3 fault runs), Mosquitto TLS, OpenPLC._

## M5 — Complete system (on the Pi)
_Added at M5: rig, 20-part test, 10-minute run, power-cycle test._
