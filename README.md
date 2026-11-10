# Edge Inspection — Edge AI & Embedded Vision Systems

[![tests](https://github.com/mkarthikaravind1/Edge_AI_Project/actions/workflows/tests.yml/badge.svg)](https://github.com/mkarthikaravind1/Edge_AI_Project/actions/workflows/tests.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/mkarthikaravind1/Edge_AI_Project)

**Karthik Aravind M (S10)** · a complete edge visual-inspection station for my IDRP 3D-printed enclosure:
camera → INT8 detector → pass/fail inspection → decision → relay/LED + PLC + secure MQTT → live dashboard,
with motor-vibration monitoring, OTA updates and fail-safe behaviour. Built to run on a Raspberry Pi with a USB webcam,
in Docker, starting by itself after a power cycle. **Status: M1 and M2 are measured on my Raspberry Pi 5 (6 Nov 2026,
[M1 Pi run](evidence/M1/PI_RUN.md), [M2 Pi run](evidence/M2/PI_RUN.md)); M3–M5 are measured on my laptop so far, their
Pi runs follow [docs/PI_CHECKLIST.md](docs/PI_CHECKLIST.md). For M3–M5 there is also 👥 group-run evidence from the
shared Raspberry Pi 5 rig (filmed by me), kept in each milestone's index and listed apart from my own numbers.**

Objects (classes): **enclosure** (my closed printed part), **body** = Model 1, **lid** = Model 2 — both models split
from my CAD file `cad/enclosure_full.stl`.

![software stack](docs/stack.png)

## How it works (one paragraph)
`hal/` hides the hardware (USB webcam / video / image folder / Picamera2, console ↔ GPIO relay, CSV ↔ MPU6050, fake ↔ Modbus), so the same
code runs on the laptop and the Pi (`EDGE_TARGET=laptop|pi`). A YOLOv8n trained on my own labelled frames and CAD
renders, quantised to **TFLite INT8 (3.2 MB)**, finds the part; `inspect.py` checks it against limits learned from
good parts only; a **3-of-5 debounce** turns frames into one decision per part; a `reject` output pulses and the PLC
counts; a `run_permit` relay is on only while the system is healthy, so a lost camera, a crash or a power cut all stop
the line. Everything is published on an internal bus that feeds **MQTT over TLS**, the **dashboard** and the logs.
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Results so far (M1–M2 on the Raspberry Pi 5; M3–M5 on the laptop, Pi runs follow [docs/PI_CHECKLIST.md](docs/PI_CHECKLIST.md))

| Milestone | Key measured numbers | Evidence |
|---|---|---|
| **M1 Detect** | real test mAP@0.5 **0.995**, mAP@0.5:0.95 0.995 (real val 0.991 / 0.951); 10 wrong detections analysed; **on the Pi 5: live overlay 15.5 FPS (camera-limited), frame latency median 19.3 ms / p95 23.1 ms, CPU 28 %, 61 °C**; laptop 68.6 FPS | [M1 index](evidence/M1/README.md), [TARGETS](docs/TARGETS.md), [DATA_CARD](docs/DATA_CARD.md) |
| **M2 Optimize** | TFLite INT8 **3.2 MB**, mAP@0.5 drop **0.001** vs its FP32; ONNX INT8 3.6 MB, drop 0.024; fair benchmark (20 warm-up, 200 runs) **on the Pi 5: TFLite INT8 inference median 16.0 ms (54 FPS model-only), 1.5–2× faster than FP32; INT8 runs live on the Pi; all 4 own targets met on the Pi** | [M2 index](evidence/M2/README.md), [comparison](evidence/M2/comparison.md), [OPTIMISATION](docs/OPTIMISATION.md) |
| **M3 Decide & Act** | one bad frame never fires, 3-in-a-row does; safe state **1.06 s** after camera loss; 2 streams × 30 FPS; frame→actuator p95 **8.8 ms** (part→actuator 75 ms)<br>👥 **Group run on the Pi 5:** group's PPE detector switching 3 LEDs live on the breadboard (45 s video), Pi dashboard about 5 FPS | [M3 index](evidence/M3/README.md), [group rig](evidence/M3/README.md#group-rig-shared-raspberry-pi-5), [DECISION_RULES](docs/DECISION_RULES.md) |
| **M4 Monitor & Connect** | MQTT security **6/6**; 3 topics, 0 schema failures; PLC 7/7 pulses; OTA v1→v2, broken v3 rolled back, tampered refused; restart after crash **1.2 s**; motor alert 1.0 s (synthetic IMU)<br>👥 **Group servo monitor (Arduino → Pi 5):** real sensor stream (6 videos, recorded CSV), live anomaly video and dashboard "ANOMALY DETECTED"; group-reported: 0 false alarms in 150 normal cycles, TLS on 8883, Modbus to a software client (no physical PLC), USB reconnect 4.98 s; [photos & videos (Drive)](https://drive.google.com/drive/folders/1Rb_cH2TGkXbIfMN6ufUxH2sYoraduzOa?usp=sharing) | [M4 index](evidence/M4/README.md), [group rig](evidence/M4/README.md#group-rig-shared-raspberry-pi-5), [MQTT_TOPICS](docs/MQTT_TOPICS.md), [THREAT_MODEL](docs/THREAT_MODEL.md) |
| **M5 Complete system** | 10-min full chain: **30.0 FPS**, 0 errors, 171/172 parts tracked, 1858 MQTT msgs, part→reject p95 90 ms; 20-part stand-in test **16/20, false-pass 0.30 (target 0.10 not met yet — rig test pending)**; readiness 7/7<br>👥 **Group integrated system (PPE station + servo monitor, on a Windows laptop, motor data replayed from the Pi rig):** 10-min chain 4.0 FPS, 0 errors; 20/20 test images correct (dashboard running total 78.6 %, false-pass 9.52 %); live dashboard with 3 KPIs and motor alert | [M5 index](evidence/M5/README.md), [group system](evidence/M5/README.md#group-system-m5-integrated-dashboard), [DEFECTS](docs/DEFECTS.md), [DEMO](docs/DEMO.md) |

Everything measured is in `evidence/` and collected in [docs/RESULTS.md](docs/RESULTS.md) (`python scripts/make_report.py`).
Every evidence json records the host it ran on: laptop numbers are never presented as Pi numbers.

## Quick start — laptop
```bash
py -3.12 -m venv .venv
.venv\Scripts\activate            # Pi/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest -q                         # 35 tests
python scripts/station_sim.py --minutes 2        # full station on a simulated conveyor -> http://localhost:8000
python -m edgevision.app --dashboard --inspect   # with the webcam
```
Docker on the laptop: `docker compose -f docker/compose.yaml -f docker/compose.laptop.yaml up -d --build`.

## Run it online (GitHub Codespaces, nothing to install)
1. Click **Open in GitHub Codespaces** above (or **Code → Codespaces → Create codespace on main**); wait ~3 min
   while `.devcontainer/devcontainer.json` installs the Pi's packages.
2. In the terminal: `python scripts/station_sim.py --minutes 30 --auto-truth`
3. **PORTS** tab → port 8000 → globe icon: the live dashboard (simulated conveyor of real + simulated rig images,
   synthetic motor fault at 40–55 s). The port is private (your GitHub login); set it to *Public* only for a demo.
4. Stop the codespace when done (free tier: 60 core-hours / month).
Tests run automatically on every push (badge above, `.github/workflows/tests.yml`).

## Quick start — Raspberry Pi
Flash **Raspberry Pi OS (Legacy, 64-bit) = Bookworm** with Raspberry Pi Imager (hostname `pi-karthik`, your own
user, Wi-Fi, SSH), plug the USB webcam in, then on the Pi (the repo is public, no GitHub login needed to clone) — one
command that installs, reboots, continues by itself and then offers every milestone from a menu:
```bash
git clone https://github.com/mkarthikaravind1/Edge_AI_Project.git ~/Edge_AI_Project && bash ~/Edge_AI_Project/deploy/start_here.sh
```
(or copy `deploy/start_here.sh` onto the SD card's bootfs drive and run `bash /boot/firmware/start_here.sh`).
No LED/relay wired yet: the Pi's own **green ACT** LED is the reject output and the **red PWR** LED shows run-permit.
`pi_evidence.sh m3` builds the Docker stack and installs `deploy/install_service.sh compose` (starts at every boot,
for any username). `bash deploy/kiosk.sh install` makes the monitor open the dashboard full-screen after boot.
Dashboard: `http://localhost:8000` on the Pi, `http://pi-karthik.local:8000` from a phone on the same Wi-Fi.

## Repository map
| Path | What |
|---|---|
| `src/edgevision/hal/` | camera, actuator, IMU, PLC interfaces + laptop fakes + Pi implementations |
| `src/edgevision/detect/` | detector interface; PyTorch, ONNX Runtime, TFLite backends |
| `src/edgevision/runtime.py`, `app.py` | the station loop, camera watchdog, entry point |
| `src/edgevision/decide/` | N-of-M debounce, one trigger per part, safe state, part tracking |
| `src/edgevision/inspect.py` | pass/fail checks (mark, chipped corner, lid missing / not seated) |
| `src/edgevision/monitor/` | IMU features, normal-only anomaly model, live alert |
| `src/edgevision/comms/mqtt.py` | MQTT over TLS bridge |
| `src/edgevision/ops/` | OTA (hash → health check → rollback), health check, rotating logs |
| `src/edgevision/dashboard/` | FastAPI REST + WebSocket + MJPEG, static web UI (offline) |
| `scripts/` | data pipeline, training (Colab), export/quantise, evaluate, benchmarks, every evidence script |
| `docker/`, `deploy/` | Dockerfile, compose, Mosquitto TLS config, systemd units, OTA bundles, OpenPLC program |
| `cad/` | my CAD: full enclosure, Model 1 (body), Model 2 (lid) |
| `docs/` | see below |
| `evidence/M1..M5/` | every measured number (json/csv/png/log); each folder's `README.md` maps checklist item → result → files |

## Documents
[DATASHEET](docs/DATASHEET.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [TARGETS](docs/TARGETS.md) ·
[DATA_CARD](docs/DATA_CARD.md) · [OPTIMISATION](docs/OPTIMISATION.md) · [DECISION_RULES](docs/DECISION_RULES.md) ·
[MQTT_TOPICS](docs/MQTT_TOPICS.md) · [THREAT_MODEL](docs/THREAT_MODEL.md) · [DEFECTS](docs/DEFECTS.md) · [RIG](docs/RIG.md) ·
[DEMO (live demo script + video shot list)](docs/DEMO.md) · [PI_CHECKLIST](docs/PI_CHECKLIST.md) · [VIVA_NOTES](docs/VIVA_NOTES.md) ·
[RESULTS](docs/RESULTS.md)

## Honest limits
- Training data: one 74 s video on one desk + CAD renders; test set is 18 real frames → M1 scores are "same scene".
- Motor model and false alarms are from **synthetic** IMU data until the MPU6050 runs are recorded on the Pi.
- Pass/fail is measured on a laptop stand-in with **simulated** marks/chips; chipped corners are not caught yet.
- Pi FPS, latency and temperature for M1–M2 are measured on the Pi 5 (no cooler fitted); M3–M5 device numbers
  (frame→actuator on the Pi, cold boot, OpenPLC, real IMU, rig pass/fail) are still pending the Pi.
- 👥 Group evidence for M3–M5 is the group's systems (PPE detector, SG90 servo monitor), not my enclosure station; my
  part was filming. Group M4 reports and logs are written up by the group's script from my group member's
  measurements (marked *group-reported*); the group's M5 ran on a Windows laptop with the motor data replayed, and its
  "50 samples" reuse 20 images.
