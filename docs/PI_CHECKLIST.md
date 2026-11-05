# Raspberry Pi checklist

Everything that must be **measured on the Pi** is here, with the exact commands and where the result lands.
Laptop numbers never count as device results; every evidence json records `host.device_type`.

---

## Fast path (recommended): two scripts do everything below

```bash
git clone https://github.com/mkarthikaravind1/Edge_AI_Project.git ~/Edge_AI_Project
bash ~/Edge_AI_Project/deploy/pi_setup.sh          # section 0 in one go; reboot when told, run it once more
cd ~/Edge_AI_Project
bash scripts/pi_evidence.sh m1                     # then m2, m3, coldboot, m4, m5
```
`pi_evidence.sh` runs every measurement in the tables below, **pauses for each hands-on step** (wiring, unplugging
the camera, passing parts, injecting the motor fault) and prints the `git add / commit / push` commands at the end of
each milestone; it never commits by itself. Suggested order with the 10 Nov deadline: day 1 setup + m1 + m2,
day 2 m3 + coldboot, day 3 m4, day 4 rig + m5 + demo rehearsal. The sections below are the same steps by hand.

## Hardware on this rig
- Raspberry Pi + monitor (HDMI) + keyboard/mouse, **one USB webcam** (the mentor's) in a USB port. No Pi Camera Module.
- `config/pi.yaml`: `camera: webcam, index: auto` (found by its `/dev/v4l/by-id/` name, so it is the same camera after
  the unplug test). Stream 2 of the two-stream test replays the committed real test frames (`camera2: images`);
  with a second webcam set `camera2: {type: webcam, index: /dev/video2}` instead.
- Only **one program can open the webcam**. From M3 on the station runs at boot and holds it; `pi_evidence.sh` stops
  the station before every step that opens the camera itself and starts it again afterwards.

## 0. One-time setup (fresh Raspberry Pi OS 64-bit, Bookworm)

**Which image:** Raspberry Pi Imager → *Raspberry Pi OS (other)* → **Raspberry Pi OS (Legacy, 64-bit)** = Bookworm.
The newest default image is Trixie (Python 3.13): `requirements-pi.txt` pins numpy 1.x for Bookworm, so `pi_setup.sh`
stops on any other release (override with `FORCE_OS=1`).

In Imager's *Edit settings*: hostname **`pi-karthik`**, any username + password (the services are filled in for your
user by `deploy/install_service.sh`), Wi-Fi, **enable SSH**. The repo is public: cloning needs no GitHub login; pushing
evidence back needs a GitHub Personal Access Token as the password (or copy the files to the laptop and push there).

Then on the Pi:

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
v4l2-ctl --list-devices                    # USB webcam visible? (sudo apt install v4l-utils)
ls -l /dev/v4l/by-id/                      # its stable name (index: auto uses the *-video-index0 link)
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

### Wiring (Pi powered OFF while wiring)
| Signal | Pi pin (BCM) | Physical pin | Goes to | Meaning |
|---|---|---|---|---|
| run_permit | GPIO17 | 11 | relay module IN1 | relay energised = conveyor/motor allowed; OFF = STOP (safe state) |
| reject | GPIO27 | 13 | LED anode via 330 Ω (or relay IN2) | pulses 0.5 s when the rule fires |
| 5 V | 5V | 2 | relay module VCC | |
| GND | GND | 6 (and 14 for the LED) | relay GND, LED cathode | common ground |

Motor/conveyor supply goes through relay 1 **COM → NO** contact, so it only runs while the relay is energised.
If your relay board is active-LOW (most cheap blue boards: "low level trigger"), set `active_high: false` in `config/pi.yaml`.

Quick output test (no camera needed):
```bash
python -c "from gpiozero import LED; import time; r=LED(17); l=LED(27); r.on(); l.blink(0.2,0.2,5,False); r.off()"
```

### Measurements
| # | Command (on the Pi, venv active, `EDGE_TARGET=pi`) | Result file |
|---|---|---|
| 3.2 | `python scripts/two_stream.py --seconds 30` (stream 1 = USB webcam live, stream 2 = committed real test frames; second webcam: see *Hardware on this rig*) | `evidence/M3/two_stream_pi.json` |
| 3.3 | `python scripts/debounce_demo.py` | `evidence/M3/debounce_demo.json/.csv` |
| 3.4 | `python scripts/safe_state_demo.py --live --seconds 40` — at ~10 s **unplug the USB webcam**, at ~25 s plug back (watch relay 1 click off and on; film it) | `evidence/M3/safe_state.json` |
| 3.6 | `python scripts/e2e_latency.py --live --events 25` — slide a closed enclosure under the camera and away again, every ~3 s | `evidence/M3/e2e_latency_pi.json` |

### Docker + cold boot (3.5)
```bash
cd ~/Edge_AI_Project
echo "MQTT_PASSWORD=<the password from the M4 step>" > docker/.env      # compose refuses to start without it
docker compose -f docker/compose.yaml build                            # ~10-15 min the first time
docker compose -f docker/compose.yaml up -d
docker logs -f edge                                                    # see frames / triggers; Ctrl+C to leave
bash deploy/install_service.sh compose      # fills in your username + repo path, enables it at boot
```
Cold-boot test (film it): `sudo poweroff` → pull the power → plug in → wait ~60 s without touching anything →
show `docker ps` (both containers *Up*) and trigger the relay by putting a part in view. Save the output:
`docker ps > evidence/M3/cold_boot_docker_ps.txt; uptime >> evidence/M3/cold_boot_docker_ps.txt; docker logs edge --since 5m > evidence/M3/cold_boot_edge.log`

## M4 — Monitor and connect (on the Pi)

### 4.1 MPU6050 wiring (Pi OFF while wiring)
| MPU6050 pin | Pi physical pin | Pi function |
|---|---|---|
| VCC | 1 | 3.3 V (the GY-521 board also accepts 5 V; 3.3 V is safer for the I²C lines) |
| GND | 9 | GND |
| SDA | 3 | GPIO2 / SDA1 |
| SCL | 5 | GPIO3 / SCL1 |
| AD0 | leave open (or GND) | address 0x68 |
Mount it firmly on the motor housing/bracket (double-sided tape or a screw), same spot for every run.
Check: `i2cdetect -y 1` shows **68**.

### 4.1 Record the runs (motor running, 30 s each, keep everything else the same)
```bash
for i in 1 2 3 4 5 6 7 8; do python scripts/record_imu.py --label normal --run $i --seconds 30; done   # 8 normal
python scripts/record_imu.py --label fault_unbalance --run 1 --seconds 30   # coin/blu-tack stuck on the rotor/fan
python scripts/record_imu.py --label fault_unbalance --run 2 --seconds 30   # bigger weight
python scripts/record_imu.py --label fault_tap --run 1 --seconds 30         # tap the mount about once a second
```
Normal 1–2 train, 3 sets the threshold, 4–8 are the **5 unseen normal runs** for false alarms. Fault runs: ≥ 3.
(Take a photo of the set-up and of each fault you inject: `evidence/M4/imu_setup.jpg`.)

### 4.2 / 4.3 Train + false alarms + live alert
```bash
python scripts/train_anomaly.py --data data/imu/real           # -> evidence/M4/anomaly_model.json, false_alarms.json, anomaly_scores.png
python scripts/motor_monitor.py --live --seconds 40             # press ENTER when you inject the fault -> evidence/M4/live_alert.json
```

### 4.4 Broker with TLS on the Pi
```bash
bash docker/mosquitto/make_certs.sh $(hostname -I | awk '{print $1}')   # CA + server cert incl. the Pi's IP
python docker/mosquitto/make_passwd.py                                   # random passwords -> docker/.env, hashes -> passwd
chmod 600 docker/.env && chmod 640 docker/mosquitto/passwd
docker compose -f docker/compose.yaml up -d mosquitto
python scripts/mqtt_security_test.py                                    # -> evidence/M4/mqtt_security.json (expect 6/6)
docker logs mosquitto > evidence/M4/mosquitto_broker_pi.log 2>&1
```

### 4.5 Topics
Start the station (`docker compose -f docker/compose.yaml up -d`), then from the laptop or the Pi:
`python scripts/mqtt_subscribe.py --seconds 60 --save evidence/M4/mqtt_topics_sample_pi.json` (show a part + shake the motor).

### 4.6 OpenPLC (Modbus TCP on 502)
```bash
cd ~ && git clone https://github.com/thiagoralves/OpenPLC_v3.git && cd OpenPLC_v3 && ./install.sh linux   # ~20 min ("rpi" option needs wiringPi, which Bookworm no longer has)
sudo systemctl enable --now openplc       # web UI http://<pi>:8080  (login openplc / openplc -> CHANGE IT)
```
In the web UI: **Hardware → "Blank"** (GPIO17/27 belong to the station) → **Programs → upload
`deploy/openplc/edge_tags.st`** → compile → **Start PLC** → **Monitoring** shows `reject_coil` (%QX0.0),
`part_count` (%QW0), `plc_reject_total` (%QW1). Then on the Pi:
```bash
python scripts/plc_watch.py --seconds 60        # while parts pass the camera -> evidence/M4/plc_link_pi.json
```
Film the OpenPLC Monitoring page while a part triggers (`evidence/M4/openplc_monitoring.png` screenshot).
Firewall (Modbus has no password): `sudo ufw allow 22,8000,8883/tcp && sudo ufw default deny incoming && sudo ufw enable`.

### 4.8 Reliability
```bash
python scripts/drift_report.py --live --seconds 30                                # -> evidence/M4/drift_report.json/png
docker exec edge python scripts/ota.py install /app/deploy/ota/bundles/edge-v1.tar.gz && docker restart edge
docker exec edge python scripts/ota.py install /app/deploy/ota/bundles/edge-v2.tar.gz && docker restart edge
docker exec edge python scripts/ota.py install /app/deploy/ota/bundles/edge-v3-broken.tar.gz   # -> "rolled back to v2"
docker logs edge 2>&1 | grep "release=" | tail -2                                 # shows the station runs v2
# auto-restart after a forced crash:
docker exec edge sh -c 'kill -USR1 1'; sleep 8;   # from INSIDE: 'docker kill' counts as a manual stop and is never restarted
 docker ps --filter name=edge; docker inspect -f '{{.RestartCount}}' edge
docker logs edge 2>&1 | grep -E "FORCED CRASH|station starting" | tail -3 > evidence/M4/crash_restart_pi.log
```

## M5 — Complete system (on the Pi)

| # | Do | Result file |
|---|---|---|
| 5.1 | Build the rig (`docs/RIG.md`), photo of it; `python scripts/capture_frame.py --name rig_view` | `evidence/M5/rig_photo.jpg`, `rig_view.png` |
| 5.2 | `python scripts/capture_rig.py` (≈15 calib, 10 good, 10 defective) → `python scripts/calibrate_inspection.py --dir data/rig/calib_good` → `python scripts/passfail_test.py --dir data/rig/test` | `evidence/M5/passfail.json`, `passfail_confusion.png`, `passfail_sheet.jpg` |
| 5.3 | Full chain 10 min: `docker compose -f docker/compose.yaml up -d`, pass parts by hand every few seconds, shake the motor once; meanwhile `python scripts/mqtt_subscribe.py --seconds 600 --save evidence/M5/full_chain_mqtt_pi.json`. Afterwards `curl -s localhost:8000/api/stats > evidence/M5/full_chain_pi_stats.json; curl -s localhost:8000/api/kpis > evidence/M5/full_chain_pi_kpis.json; docker logs edge --since 11m > evidence/M5/full_chain_pi.log 2>&1` | the 4 files |
| 5.3b | Monitor shows the dashboard after boot: `bash deploy/kiosk.sh install`, `sudo reboot` (leave kiosk: Alt+F4) | photo of the monitor |
| 5.4 | Dashboard on a phone: `http://pi-karthik.local:8000` → screenshot | `evidence/M5/dashboard_phone_pi.png` |
| 5.5 | Power cycle (pull the plug), wait 90 s, then `python scripts/readiness_check.py --pi`; repeat the last check **with Wi-Fi off / cable out** (`sudo nmcli radio wifi off`, then back `on`) | `evidence/M5/readiness_pi.json` |
| 5.6 | Headline metric: mark every part on the dashboard during 5.3; `curl -s localhost:8000/api/kpis` shows `headline` | in `full_chain_pi_kpis.json` |
| 5.8 | Rehearse `docs/DEMO.md` once with a timer; record the demo video | `evidence/M5/demo.mp4` (`git add -f`) |

Enable inspection permanently on the Pi after 5.2: in `config/pi.yaml` set `inspection.enabled: true`
(compose already starts the app with `--inspect`).
