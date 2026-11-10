# M3 — Decide and Act: evidence

One section per task on the marking sheet. Each section shows what the task asks for, what I measured so far, the
files, and a place for the **group run on the Pi** (photos in this folder, videos as Drive/YouTube links).

**Where it ran:** 💻 = measured on my laptop (every json records its host) · 👥 Pi = group run on the shared Pi rig.
Laptop numbers are never presented as Pi numbers. Pi commands: [PI_CHECKLIST § M3](../../docs/PI_CHECKLIST.md#m3--decide-and-act-on-the-pi).

**Group media rule:** every photo/video from the group session is labelled *"group run on the shared Pi rig — my part:
… — filmed by …"*. My own measured numbers are listed separately from the group media.

### Group rig (shared Raspberry Pi 5)

The group session ran on one shared rig. The group's system on it is the helmet/glove (PPE) detector, which uses its
own model and 3 LEDs. My enclosure-inspection code is a separate system. Group media below shows that rig, not my
numbers.

| Part | On the group rig |
|---|---|
| Board | Raspberry Pi 5 ([group_pi5_board.jpg](group_pi5_board.jpg)) |
| Camera | Arducam UC-844 (USB) |
| Outputs | 3 LEDs on a breadboard, 220 Ω each: green GPIO27 (pin 13), yellow GPIO17 (pin 11), red GPIO22 (pin 15), GND pin 14 ([group_led_breadboard.jpg](group_led_breadboard.jpg)) |
| Walk-through video | [group_pi_setup.mp4](group_pi_setup.mp4) (13 s) |

**My outputs on this rig:** my `reject` is GPIO27 and `run_permit` is GPIO17, the same pins as the green and yellow
LEDs. Running my code on the group breadboard therefore needs no change: **green LED = `reject`** (pulses per part),
**yellow LED = `run_permit`** (on while healthy, off in SAFE STATE). The red LED (GPIO22) is not used by my code.

Group media caption: *group run on the shared Pi rig — my part: filming the group run — filmed by me* (all group photos and videos in
this folder).

| Task | Max | Measured so far | Section |
|---|---|---|---|
| Decision rule sheet | 3 | input, 0.60 threshold, 3-of-5, action, safe state written and tested | [3.1](#31-decision-rule-sheet) |
| Two-stream pipeline | 4 | 2 streams × 29.8 FPS at once (laptop) | [3.2](#32-two-stream-pipeline) |
| Debounce | 4 | 1 bad frame: no trigger; 3 in a row: trigger | [3.3](#33-debounce) |
| Actuator fires | 3 | run_permit off 1.06 s after camera loss; reject pulse per part; 👥 Pi video of 3 LEDs firing | [3.4](#34-actuator-fires) |
| Docker | 4 | container built, healthy, restart policy + systemd unit | [3.5](#35-docker) |
| End-to-end latency | 2 | 25 events: frame → actuator p95 8.8 ms (laptop) | [3.6](#36-end-to-end-latency) |

---

## 3.1 Decision rule sheet

**Asked:** write the input, threshold, action and safe state if the camera fails.

Rule sheet: [docs/DECISION_RULES.md](../../docs/DECISION_RULES.md).

| Item | Value |
|---|---|
| Input | detections from the INT8 YOLOv8n every frame; class `enclosure` (M5: the inspection verdict `FAIL`) |
| Threshold | confidence ≥ **0.60** — on 54 real frames all 77 correct detections were ≥ 0.61, 7 of 11 false ones < 0.60 |
| Debounce | fire when ≥ **3 of the last 5** frames are hits; one trigger per part (re-arm after 5 empty frames) |
| Action | `reject` output pulses 0.5 s, PLC coil %QX0.0 pulses, register %QW0 counts, MQTT `detection` message |
| Safe state | no frame for **1.0 s** → `run_permit` relay off = conveyor STOP; back on with the first good frame |

Code: [src/edgevision/decide/rules.py](../../src/edgevision/decide/rules.py), config `decide:` in
[config/pi.yaml](../../config/pi.yaml), tests [tests/test_decide.py](../../tests/test_decide.py).

## 3.2 Two-stream pipeline

**Asked:** run two streams at once and show FPS per stream.

💻 Laptop, 15 s per mode, TFLite INT8 ([two_stream_laptop.json](two_stream_laptop.json)):

| Mode | Stream 1 FPS | Stream 2 FPS | Errors |
|---|---|---|---|
| Real time, one shared model | 29.77 | 29.72 | 0 |
| Real time, a model per stream | 29.91 | 29.89 | 0 |
| Flat out, shared model | 84.3 | ~84 | 0 |

Both streams hold the camera rate (30 FPS). A shared model needs a lock, so the streams take turns; separate models
use more memory but run in parallel. Code: [scripts/two_stream.py](../../scripts/two_stream.py).

## 3.3 Debounce

**Asked:** show one bad frame does not trigger and N frames in a row do.

💻 Real model on real images, rule 3-of-5 at conf ≥ 0.60 ([debounce_demo.json](debounce_demo.json), frame log [debounce_demo.csv](debounce_demo.csv)) — **passed**:
- frame 6: a single part frame → **no trigger**
- frame 15: 3rd hit in a row → **trigger**; the same part stays in view → HOLD, no second trigger
- frame 59: the next part → **trigger** again

Code: [scripts/debounce_demo.py](../../scripts/debounce_demo.py); unit tests [tests/test_decide.py](../../tests/test_decide.py).

## 3.4 Actuator fires

**Asked:** make the relay, LED or conveyor-stop signal work live.

- Outputs: `reject` (GPIO27, LED / relay 2) pulses 0.5 s per part; `run_permit` (GPIO17, relay 1) is on only while
  the system is healthy. On the Pi without wiring, the board's green ACT LED is `reject` and the red PWR LED shows `run_permit`.
- 💻 Safe state measured: camera stopped at 4.0 s → `run_permit` **off 1.06 s after the last frame** (timeout 1.0 s),
  back on at 8.0 s with the first good frame ([safe_state.json](safe_state.json), [safe_state_log.csv](safe_state_log.csv)).
- Code: [src/edgevision/hal/actuator.py](../../src/edgevision/hal/actuator.py), [scripts/safe_state_demo.py](../../scripts/safe_state_demo.py).

👥 **Group run on the Pi 5** (group's PPE system, live Arducam camera):
- [group_3led_actuator.mp4](group_3led_actuator.mp4) (45 s): the breadboard LEDs switch live as a helmet and a glove
  are shown to the camera; the Pi dashboard runs alongside.
- [group_led_breadboard.jpg](group_led_breadboard.jpg): the wired breadboard with LEDs lit.
- [group_pi_dashboard_frame.png](group_pi_dashboard_frame.png): frame from that video. The dashboard reads host
  Raspberry Pi 5, sensor Arducam UC-844, about 5 FPS and 140–195 ms latency for the group's model (read off the
  screen, not a measurement of mine).

## 3.5 Docker

**Asked:** build and start the container from a cold boot and trigger the actuator.

- Image: [docker/Dockerfile](../../docker/Dockerfile) (Debian Bookworm, same as Raspberry Pi OS); stack:
  [docker/compose.yaml](../../docker/compose.yaml) with `restart: unless-stopped` and a healthcheck on `/api/health`.
- Starts at every boot: [deploy/edge-compose.service](../../deploy/edge-compose.service), installed by
  [deploy/install_service.sh](../../deploy/install_service.sh).
- 💻 Laptop: container `edge` **Up (healthy)**, 29.8 FPS ([docker_healthy_laptop.txt](../M5/docker_healthy_laptop.txt)).

## 3.6 End-to-end latency

**Asked:** measure frame-to-actuator latency over 20+ events.

💻 Laptop, **25 events**, 30 FPS, TFLite INT8, rule 3-of-5 ([e2e_latency_laptop.json](e2e_latency_laptop.json), per event [e2e_latency_laptop.csv](e2e_latency_laptop.csv)):

| Measured from | Median | p95 | Max | Target p95 |
|---|---|---|---|---|
| frame that fired → actuator command | **6.6 ms** | **8.8 ms** | 24.8 ms | ≤ 600 ms ✅ |
| part's first frame → actuator command (includes the deliberate 3-of-5 wait) | 73.1 ms | 75.4 ms | 91.4 ms | ≤ 600 ms ✅ |

Code: [scripts/e2e_latency.py](../../scripts/e2e_latency.py).

---
More: [VIVA_NOTES § M3](../../docs/VIVA_NOTES.md#m3-decide-and-act) · all numbers: [RESULTS § M3](../../docs/RESULTS.md#m3)
