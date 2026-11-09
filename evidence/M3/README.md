# M3 — Decide and Act: evidence

One section per task on the marking sheet. Each section shows what the task asks for, what I measured so far, the
files, and a place for the **group run on the Pi** (photos in this folder, videos as Drive/YouTube links).

**Where it ran:** 💻 = measured on my laptop (every json records its host) · 👥 Pi = group run on the shared Pi rig,
media to add. Laptop numbers are never presented as Pi numbers. Pi commands: [PI_CHECKLIST § M3](../../docs/PI_CHECKLIST.md#m3--decide-and-act-on-the-pi).

**Group media rule:** every photo/video from the group session is labelled *"group run on the shared Pi rig — my part:
… — filmed by …"*. My own measured numbers are listed separately from the group media.

| Task | Max | Measured so far | Section |
|---|---|---|---|
| Decision rule sheet | 3 | input, 0.60 threshold, 3-of-5, action, safe state written and tested | [3.1](#31-decision-rule-sheet) |
| Two-stream pipeline | 4 | 2 streams × 29.8 FPS at once (laptop) | [3.2](#32-two-stream-pipeline) |
| Debounce | 4 | 1 bad frame: no trigger; 3 in a row: trigger | [3.3](#33-debounce) |
| Actuator fires | 3 | run_permit off 1.06 s after camera loss; reject pulse per part | [3.4](#34-actuator-fires) |
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

👥 **Group run on the Pi** — two-stream FPS photo/video: _to add_ (`two_stream_pi.json` if recorded).

## 3.3 Debounce

**Asked:** show one bad frame does not trigger and N frames in a row do.

💻 Real model on real images, rule 3-of-5 at conf ≥ 0.60 ([debounce_demo.json](debounce_demo.json), frame log [debounce_demo.csv](debounce_demo.csv)) — **passed**:
- frame 6: a single part frame → **no trigger**
- frame 15: 3rd hit in a row → **trigger**; the same part stays in view → HOLD, no second trigger
- frame 59: the next part → **trigger** again

Code: [scripts/debounce_demo.py](../../scripts/debounce_demo.py); unit tests [tests/test_decide.py](../../tests/test_decide.py).

👥 **Group run on the Pi** — video of the trigger LED with one bad frame vs a real part: _to add_.

## 3.4 Actuator fires

**Asked:** make the relay, LED or conveyor-stop signal work live.

- Outputs: `reject` (GPIO27, LED / relay 2) pulses 0.5 s per part; `run_permit` (GPIO17, relay 1) is on only while
  the system is healthy. On the Pi without wiring, the board's green ACT LED is `reject` and the red PWR LED shows `run_permit`.
- 💻 Safe state measured: camera stopped at 4.0 s → `run_permit` **off 1.06 s after the last frame** (timeout 1.0 s),
  back on at 8.0 s with the first good frame ([safe_state.json](safe_state.json), [safe_state_log.csv](safe_state_log.csv)).
- Code: [src/edgevision/hal/actuator.py](../../src/edgevision/hal/actuator.py), [scripts/safe_state_demo.py](../../scripts/safe_state_demo.py).

👥 **Group run on the Pi** — video of the relay/LED firing when a part is shown, and stopping when the webcam is
unplugged: _to add_.

## 3.5 Docker

**Asked:** build and start the container from a cold boot and trigger the actuator.

- Image: [docker/Dockerfile](../../docker/Dockerfile) (Debian Bookworm, same as Raspberry Pi OS); stack:
  [docker/compose.yaml](../../docker/compose.yaml) with `restart: unless-stopped` and a healthcheck on `/api/health`.
- Starts at every boot: [deploy/edge-compose.service](../../deploy/edge-compose.service), installed by
  [deploy/install_service.sh](../../deploy/install_service.sh).
- 💻 Laptop: container `edge` **Up (healthy)**, 29.8 FPS ([docker_healthy_laptop.txt](../M5/docker_healthy_laptop.txt)).

👥 **Group run on the Pi** — cold boot (pull the plug → plug in → hands off → `docker ps` shows the containers Up →
part shown → actuator fires): video and `cold_boot_docker_ps.txt` _to add_.

## 3.6 End-to-end latency

**Asked:** measure frame-to-actuator latency over 20+ events.

💻 Laptop, **25 events**, 30 FPS, TFLite INT8, rule 3-of-5 ([e2e_latency_laptop.json](e2e_latency_laptop.json), per event [e2e_latency_laptop.csv](e2e_latency_laptop.csv)):

| Measured from | Median | p95 | Max | Target p95 |
|---|---|---|---|---|
| frame that fired → actuator command | **6.6 ms** | **8.8 ms** | 24.8 ms | ≤ 600 ms ✅ |
| part's first frame → actuator command (includes the deliberate 3-of-5 wait) | 73.1 ms | 75.4 ms | 91.4 ms | ≤ 600 ms ✅ |

Code: [scripts/e2e_latency.py](../../scripts/e2e_latency.py).

👥 **Group run on the Pi** — `e2e_latency_pi.json` (20+ events with a real part): _to add_.

---
More: [VIVA_NOTES § M3](../../docs/VIVA_NOTES.md#m3-decide-and-act) · all numbers: [RESULTS § M3](../../docs/RESULTS.md#m3)
