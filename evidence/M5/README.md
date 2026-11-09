# M5 — Complete System + Dashboard: evidence

One section per task on the marking sheet. Each section shows what the task asks for, what I measured so far, the
files, and a place for the **group run on the Pi** (photos in this folder, videos as Drive/YouTube links).

**Where it ran:** 💻 = measured on my laptop (every json records its host) · 👥 Pi = group run on the shared Pi rig,
media to add. Laptop numbers are never presented as Pi numbers. Pi commands: [PI_CHECKLIST § M5](../../docs/PI_CHECKLIST.md#m5--complete-system-on-the-pi).

**Group media rule:** every photo/video from the group session is labelled *"group run on the shared Pi rig — my part:
… — filmed by …"*. My own measured numbers are listed separately from the group media.

| Task | Max | Measured so far | Section |
|---|---|---|---|
| Inspection rig | 2 | rig design; stand-in image set with all 4 defect types | [5.1](#51-inspection-rig) |
| Pass/fail station | 4 | 20 parts (10 good, 10 defective): 16/20, false-pass 0.30 (stand-in) | [5.2](#52-passfail-station) |
| Full chain on the device | 4 | 10 min camera → dashboard: 30.0 FPS, 0 errors; 5 breakages fixed (laptop) | [5.3](#53-full-chain-on-the-device) |
| Live dashboard | 4 | live camera + boxes, PASS/FAIL, 3 KPIs, motor alert; desktop + phone | [5.4](#54-live-dashboard) |
| Product readiness | 2 | 7/7 checks: auto-start, offline, log rotation | [5.5](#55-product-readiness) |
| Headline metric | 2 | correct parts / parts checked + false-pass rate, live on the dashboard | [5.6](#56-headline-metric) |
| Documents | 1 | README, datasheet, architecture, stack diagram, demo script — own commits | [5.7](#57-documents) |
| Live demo and questions | 1 | timed demo script: power cycle, normal run, injected fault | [5.8](#58-live-demo-and-questions) |

---

## 5.1 Inspection rig

**Asked:** show a fixed, repeatable camera and light rig and an image set with every defect type.

- Rig design: [docs/RIG.md](../../docs/RIG.md) — camera fixed at 30–45°, plain matte base, end stop so every part sits
  the same way, diffused lamp. The angle shows the side wall, which separates a closed box from a loose lid
  (M1 wrong detection #7).
- 💻 Stand-in image set (real desk frames + **simulated** marks/chips; [manifest](../../data/rig_sim/manifest.json)):
  good parts and all 4 defect types — surface mark, chipped corner, lid missing, lid not seated.
  Code: [scripts/make_sim_rig.py](../../scripts/make_sim_rig.py), real capture [scripts/capture_rig.py](../../scripts/capture_rig.py).

![stand-in image set](../../data/rig_sim/contact_sheet.jpg)

👥 **Group run on the Pi** — photo of the rig (camera, light, stop) and the image set captured on it: _to add_.

## 5.2 Pass/fail station

**Asked:** test 20 parts (10 good, 10 defective) and show the confusion matrix and false-pass rate.

💻 20 stand-in parts ([passfail.json](passfail.json), per part [passfail_results.csv](passfail_results.csv), sheet [passfail_sheet.jpg](passfail_sheet.jpg)):

| | Judged PASS | Judged FAIL |
|---|---|---|
| **Good (10)** | 9 | 1 (false reject) |
| **Defective (10)** | **3 (false pass)** | 7 |

- **16/20 correct, false-pass rate 0.30** — target ≤ 0.10 **not met yet**. Caught: marks 3/3, lid missing 3/3,
  lid not seated 1/2; chipped corners 0/2.
- How it works: the detector finds the part, then simple checks on the crop (dark marks, outline solidity,
  rectangularity) with limits learned from **good parts only** ([inspection_calibration.json](inspection_calibration.json)).
- First attempt before fixes: [passfail_v1_before_fixes.json](passfail_v1_before_fixes.json); defect list: [docs/DEFECTS.md](../../docs/DEFECTS.md).
- Code: [src/edgevision/inspect.py](../../src/edgevision/inspect.py), [scripts/calibrate_inspection.py](../../scripts/calibrate_inspection.py),
  [scripts/passfail_test.py](../../scripts/passfail_test.py).

![pass/fail confusion matrix](passfail_confusion.png)

👥 **Group run on the Pi** — 20 real parts on the rig: confusion matrix and false-pass rate: _to add_.

## 5.3 Full chain on the device

**Asked:** run camera to dashboard together for 10 minutes and fix what breaks.

💻 10 min, camera (simulated conveyor) → TFLite INT8 → inspection → decision → reject/PLC/run_permit → MQTT TLS →
dashboard, + motor monitor ([full_chain_laptop.json](full_chain_laptop.json), subscriber [full_chain_mqtt_laptop.json](full_chain_mqtt_laptop.json)):

| Measured | Value |
|---|---|
| FPS mean / min | **30.0** / 29.7 |
| Errors / safe-state events | **0** / 0 |
| Parts tracked | 171 of 172 |
| Part → reject latency median / p95 | 84 ms / **90 ms** |
| MQTT messages sent / received | 1857 / 1858, 0 schema failures |

**What broke and how I fixed it:**
1. Chain ran at **2.4 FPS** → the simulator re-blurred the empty-belt image every frame → blur once per part → 30.0 FPS for 10 min.
2. Dashboard showed "connecting…" → screenshot taken before the first WebSocket snapshot → none needed; page reconnects every 2 s.
3. KPI tiles wrapped one per row → camera spanned 3 grid rows → explicit grid placement.
4. Container crash-looped (`config/laptop.yaml` not found) → project root was found from the install path inside Docker → `EDGE_ROOT=/app` + fall back to the working directory.
5. Good parts cut by the image border judged FAIL → part not fully in view → inspector waits until the whole part is in view.

Code: [scripts/station_sim.py](../../scripts/station_sim.py), [src/edgevision/runtime.py](../../src/edgevision/runtime.py).

👥 **Group run on the Pi** — 10-minute run on the Pi with real parts (video + `full_chain_pi_stats.json`): _to add_.

## 5.4 Live dashboard

**Asked:** show live detections, PASS/FAIL view, camera view, 3 KPIs and motor alert.

- FastAPI backend (REST + WebSocket + MJPEG) and a static page; loads nothing from the internet, works offline, fits a phone.
- Shows: **live camera with boxes**, big **PASS/FAIL**, headline metric, **3 KPIs** (throughput, yield, median latency),
  **motor card** with score graph that turns red on an anomaly, parts feed with good/defective buttons.
- Code: [src/edgevision/dashboard/server.py](../../src/edgevision/dashboard/server.py), [kpis.py](../../src/edgevision/dashboard/kpis.py),
  [static/](../../src/edgevision/dashboard/static/index.html).

| 💻 Desktop | 💻 Phone |
|---|---|
| ![dashboard desktop](dashboard_desktop_laptop.jpg) | ![dashboard phone](dashboard_phone_laptop.jpg) |

👥 **Group run on the Pi** — dashboard from the Pi (`http://pi-karthik.local:8000`) on a phone, with a motor alert: _to add_.

## 5.5 Product readiness

**Asked:** show auto-start after power-cycle, offline run and logs.

💻 [readiness_laptop.json](readiness_laptop.json) — **7/7**:

| Check | Pass |
|---|---|
| dashboard loads nothing from the internet | ✅ |
| MQTT broker is local | ✅ |
| model + config are files on the device | ✅ |
| containers restart automatically (`restart: unless-stopped`) | ✅ |
| systemd unit restarts the station | ✅ |
| compose stack starts at boot ([edge-compose.service](../../deploy/edge-compose.service)) | ✅ |
| logs rotate (1 MB × 5 files + Docker 5 MB × 3) | ✅ |

Container healthy: [docker_healthy_laptop.txt](docker_healthy_laptop.txt). Code: [scripts/readiness_check.py](../../scripts/readiness_check.py)
(`--pi` adds the power-cycle and offline checks).

👥 **Group run on the Pi** — video: pull the plug → plug in → hands off → dashboard back; Wi-Fi off and still running;
`readiness_pi.json`: _to add_.

## 5.6 Headline metric

**Asked:** measure one headline number and show it live.

- Headline: **parts classified correctly out of all parts I checked**, with the **false-pass rate** beside it
  (a defective part passing is the costly error). Target ≥ 18/20 and false-pass ≤ 10 %
  ([docs/DATASHEET.md § 5](../../docs/DATASHEET.md#5-headline-metric)).
- 💻 Measured on the stand-in set: **16/20 correct, false-pass 0.30** ([passfail.json](passfail.json)).
- Live: dashboard tile and `GET /api/kpis` ([kpis.py](../../src/edgevision/dashboard/kpis.py)); the operator marks each
  part good/defective on the dashboard.

👥 **Group run on the Pi** — screenshot of the headline tile after marking the real parts: _to add_.

## 5.7 Documents

**Asked:** show my commits to the README, datasheet, architecture diagram or demo video.

| Document | Link |
|---|---|
| README | [README.md](../../README.md) |
| Datasheet | [docs/DATASHEET.md](../../docs/DATASHEET.md) |
| Architecture | [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) |
| Software stack diagram | [docs/stack.png](../../docs/stack.png) |
| Demo script + video shot list | [docs/DEMO.md](../../docs/DEMO.md) |
| Viva notes | [docs/VIVA_NOTES.md](../../docs/VIVA_NOTES.md) |

All written and committed by me: [commit history](https://github.com/mkarthikaravind1/Edge_AI_Project/commits/main).

![software stack](../../docs/stack.png)

👥 **Demo video** (group run on the Pi): _Drive/YouTube link to add_.

## 5.8 Live demo and questions

**Asked:** run one normal run and one injected fault, and answer the coach's questions.

- Timed script (~6 min): [docs/DEMO.md](../../docs/DEMO.md) — power cycle hands-off → dashboard back → **normal run**
  (3 good parts: PASS) → **injected fault** (marked and lid-missing parts: FAIL, reject pulses, PLC counts, MQTT message)
  → motor fault on the IMU → headline metric.
- Explanations for every task in simple words: [docs/VIVA_NOTES.md](../../docs/VIVA_NOTES.md).

👥 **Group run on the Pi** — demo video (normal run + injected fault): _Drive/YouTube link to add_.

---
More: [VIVA_NOTES § M5](../../docs/VIVA_NOTES.md#m5-complete-system--dashboard) · all numbers: [RESULTS § M5](../../docs/RESULTS.md#m5)
