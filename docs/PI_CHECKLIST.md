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
_Commands added when M2 is built: `benchmark_model.py` for onnx + tflite INT8 → `evidence/M2/benchmark_pi_<backend>.json`._

## M3 — Decide and act (on the Pi)
_Added at M3: GPIO wiring table, two-stream run, Docker cold-boot test, end-to-end latency._

## M4 — Monitor and connect (on the Pi)
_Added at M4: MPU6050 wiring table + recorder commands (3 normal + 3 fault runs), Mosquitto TLS, OpenPLC._

## M5 — Complete system (on the Pi)
_Added at M5: rig, 20-part test, 10-minute run, power-cycle test._
