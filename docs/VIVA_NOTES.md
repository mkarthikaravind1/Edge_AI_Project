# Viva notes — what to show and what to say

Short "explain it simply" notes per task. Commands assume the venv is active and `EDGE_TARGET` is set.

## Architecture in one breath
Core logic (detect, decide, monitor) never talks to hardware directly. It talks to a **HAL** (hardware abstraction layer):
`Camera`, `Actuator`, `Imu`, `Plc`. On the laptop these are a webcam and fakes; on the Pi they are Picamera2, GPIO, MPU6050
and Modbus. Switching is one setting in `config/<target>.yaml`, chosen by `EDGE_TARGET`.

---

## M1 Detect

**1.1 Camera & repo** — `python scripts/capture_frame.py`
> Opens the camera through the HAL, throws away 10 frames while auto-exposure settles, saves one frame and a json
> that records which machine took it.

**1.2 OpenCV pipeline** — `python scripts/run_live.py`
> Loop: read frame → detector returns boxes → `overlay.draw` paints box, class and confidence, a per-class count and FPS.
> FPS is frames counted over the last 2 seconds.

**1.3 Baseline speed** — `python scripts/benchmark_pipeline.py --seconds 60`
> 20 warm-up frames are not timed (first runs are slow: memory allocation, caches). Then for 60 s I time every frame
> from capture to overlay done, and a background thread samples CPU %, GPU % and temperature every second.
> I report median and p95, not just mean, because a few slow frames hide inside a mean.

**1.4 Dataset v1** — `extract_frames.py`, `render_cad.py`, `autolabel.py`, `check_labels.py`
> - *Blur filter:* the Laplacian highlights edges; a blurry image has few edges so its variance is low → dropped.
> - *Duplicate filter:* a perceptual hash is a 64-bit fingerprint of how the image looks; two frames whose hashes
>   differ in ≤ 6 bits are practically the same picture, so I keep only one.
> - *Synthetic:* I split my STL into body (Model 1) and lid (Model 2) and render them in random pose, light, colour
>   and background. Boxes come from the rendered pixel mask, so they are exact.
> - *Three classes:* the closed box looks different from the open tray and the loose plate, so it gets its own class
>   (`enclosure`) instead of two overlapping boxes.
> - *Auto-label, pass 1:* YOLO-World is a detector you can prompt with text ("closed white plastic box"). It found the
>   parts but mixed up the classes and missed most lids (8 lid boxes on 217 frames), so I corrected ~30 frames by hand.
> - *Auto-label, pass 2:* a helper YOLOv8n trained on those reviewed frames + the CAD renders re-labels the rest; I review
>   every frame in my offline tool (`review_labels.py`), and `reviewed.csv` proves which frames I checked and when.
>   The helper model is not my submitted model, and it only *suggests* boxes, so it cannot leak test data.

**1.5 Correct split** — `python scripts/split.py`
> Neighbouring video frames are near copies. A random split would put one copy in train and its twin in test, and the
> test score would be fake-high (**leakage**). So I cut each video into 20 time blocks and give whole blocks to one
> split, drop frames within 0.5 s of a boundary, and then pHash-check every test image against every train image (0 found).
> With only one video, a random block choice once left `enclosure` out of the test set entirely, so the script tries 500
> block assignments and keeps one where val and test contain every class at 70/20/10.
> Test is real images only, because the device will only ever see real parts.
> Augmentation (flip, small shift/scale/±5° rotation, brightness, blur, light noise) runs on train only, after the split,
> so test never contains an augmented copy of a training image.

**M2 is below M1 in this file.**

**1.6 Train & run** — `scripts/train_colab.ipynb`
> Transfer learning: start from public COCO weights (`yolov8n.pt`), fine-tune on my 3 classes (enclosure, body, lid).
> mAP@0.5 = area under the precision-recall curve, counting a box as correct if it overlaps the truth ≥ 50 %, averaged
> over classes. mAP@0.5:0.95 averages that over stricter overlaps (50 % … 95 %), so it rewards tight boxes.
> Precision = of the boxes I drew, how many were right. Recall = of the real parts, how many I found.
> **My result:** test mAP@0.5 0.995, mAP@0.5:0.95 0.995, P 0.979, R 1.000 (18 real images); real val 0.991 / 0.951.
> I picked 320 over 640: same mAP@0.5, ~4x fewer pixels, so faster on the Pi.
> **Why I don't over-trust it:** one desk, one video, 18 test images, and boxes that a model proposed.
> **One wrong detection to show** (`evidence/M1/wrong_detections/07_CLASS_val_clip1_001862.jpg`): a closed box seen from
> straight above was called "lid", because from the top both are a flat white rectangle and the side walls aren't visible.
> Fix: mount the inspection camera at an angle so the wall height shows. 6 of the 10 errors are slivers of a part cut off at
> the image edge; my labelling rule skips those, so the fix is a decision rule that ignores boxes touching the border.

---

## M2 Optimize

**2.1 Export to ONNX** — `python scripts/export.py --format onnx`
> ONNX is a standard file format for neural networks: any runtime (ONNX Runtime, TensorRT, …) can run it without PyTorch.
> Fixed batch 1 and 320×320 input, opset 13 (needed for per-channel INT8 later).

**2.2 INT8 + run live** — `python scripts/quantize_onnx.py`, `scripts/export_colab.ipynb`, `run_live.py --backend onnx --model models/best_int8.onnx`
> Quantisation maps each float to one of 256 integer steps using a scale and zero-point. To choose the scale, the
> quantiser runs 200 *calibration* images and records the range of every layer's values. They come from the train split
> only, so the model is never tuned on images I later score it on. The last ~30 nodes (box decoding) stay FP32 because
> boxes are sensitive to rounding and that part is cheap anyway.

**2.3 Accuracy check** — `python scripts/evaluate.py`
> One metric implementation for every backend, same real images. Test is saturated (1.000 for all), so I compare on the
> 36 real val frames. Each INT8 model is compared with the FP32 model of the same runtime: ONNX INT8 drops 0.024,
> TFLite INT8 drops 0.001, full-integer INT8 0.000 on mAP@0.5 (target ≤ 0.03). Full-integer loses tight boxes
> (0.934 → 0.877) because its output is int8 too: box coordinates snap to ~2.4 px steps.

**2.4 Fair benchmark** — `python scripts/benchmark_model.py --backend onnx_int8`
> Fair = same images, batch 1, same thread count, 20 warm-up runs thrown away (caches, memory allocation), 200 timed runs.
> I report the *median* (typical frame) and *p95* (bad-but-normal frame), plus the pure inference time vs the full
> detect() (pre-processing + NMS), because the live pipeline pays the full cost.

**2.5 CPU vs accelerator + stack** — `evidence/M2/comparison.md`, `docs/stack.png`
> The stack is camera → OpenCV → runtime → delegate → OS → hardware. Without an accelerator my "delegate" is XNNPACK on
> the CPU. The detector is a plug-in, so adding Coral is a config change plus an Edge-TPU-compiled model.

**2.6 Target & trade-off** — `docs/OPTIMISATION.md`
> TFLite INT8 ships: 3.8× smaller (12.1 → 3.2 MB) and almost no accuracy loss. Where you round matters: rounding the
> output costs box tightness, aggressive int8 everywhere (my ONNX INT8) costs the hard class enclosure-vs-lid.

---

## M3 Decide and Act

**3.1 Decision rule sheet** — `docs/DECISION_RULES.md`
> Input: the class `enclosure` at confidence ≥ 0.60. Fire when 3 of the last 5 frames are hits, then wait until the part
> has left (5 empty frames) before firing again, so one part = one trigger. Action: reject output pulses, PLC coil pulses,
> PLC register counts. Safe state: no frame for 1 s → run_permit relay off → conveyor stops.
> *Why 0.60:* on 54 real frames every correct detection was ≥ 0.61 and 7 of 11 false ones were below 0.60.

**3.2 Two streams** — `python scripts/two_stream.py`
> One thread per camera. A shared model needs a lock (a TFLite interpreter must not be used by two threads at once),
> so the streams take turns; separate models use more memory but infer in parallel. Laptop: both streams hold 30 FPS
> (the camera rate); flat out, shared = 84 FPS each, separate = 107 FPS each.

**3.3 Debounce** — `python scripts/debounce_demo.py`, `pytest tests/test_decide.py`
> Real model, real images: a single part frame (frame 6) does not fire; the 3rd part frame in a row (frame 15) fires;
> the same part keeps "hold"; a new part after the gap fires again (frame 59).

**3.4 Actuator + safe state** — `python scripts/safe_state_demo.py` (`--live` on the Pi, unplug the camera)
> Two outputs. *run_permit* is ON only while healthy, so *any* failure (camera lost, program crash, power cut) stops
> the conveyor: that is fail-safe by wiring, not by software. A watchdog thread checks every 50 ms; measured: off
> 1.06 s after the last frame (timeout 1.0 s), back on with the first good frame.

**3.5 Docker** — `docker/Dockerfile`, `docker/compose.yaml`, `deploy/edge-compose.service`
> Debian Bookworm base (same as Raspberry Pi OS) so the apt Picamera2/gpiozero packages work inside. `privileged` +
> `/dev` gives the container the camera, GPIO and I²C. `restart: unless-stopped` + Docker enabled at boot + the
> systemd unit bring it back after a power cycle without anyone logging in.

**3.6 End-to-end latency** — `python scripts/e2e_latency.py --events 25`
> Two numbers: from the frame that fired to the output (pipeline cost; laptop median 6.6 ms) and from the part's first
> frame to the output (adds the deliberate 3-of-5 wait = 2 frames; laptop median 73 ms at 30 FPS).

---

## M4 Monitor and Connect

**4.1 Sensor data** — `scripts/record_imu.py`, wiring in `docs/PI_CHECKLIST.md`
> MPU6050 over I²C (address 0x68): 3-axis accelerometer (g) + 3-axis gyro (°/s) at 200 Hz, saved as labelled CSVs.
> 8 normal runs + 3 fault runs (unbalance ×2, tapping). Until the Pi arrives the code is developed on clearly labelled
> SYNTHETIC runs (`data/imu/synthetic/README.md`); real runs replace them for marks.

**4.2 Anomaly model** — `scripts/train_anomaly.py`, `scripts/motor_monitor.py`
> Each 1 s window → 72 features: per axis RMS (vibration energy), peak, and FFT energy in 4 bands (0–5, 5–20, 20–50,
> 50–100 Hz). Trained on NORMAL data only: learn the mean and spread of every feature; score = how many standard
> deviations a window is away from normal (z-score distance). No fault data is needed to train, which matters because
> real faults are rare. Alert after 2 windows in a row above the threshold. Synthetic demo: alert 1.0 s after injection.

**4.3 False alarms** — `evidence/M4/false_alarms.json`
> Threshold = 99.5th percentile of scores on a normal run that was NOT used for training (the model always looks best
> on its own training data, so a training percentile would be too low). Counted on 5 more unseen normal runs.
> Synthetic: 1 false alarm in 5 runs (2.5 min), 3/3 faults detected. Trade-off: higher percentile = fewer false alarms
> but later/missed faults.

**4.4 Secure MQTT** — `scripts/mqtt_security_test.py` → 6/6
> TLS encrypts and proves the broker's identity (my own CA signed its certificate). No anonymous users, salted-hash
> password file, ACL per user. There is no plain 1883 listener at all, so a mis-configured client cannot fall back.

**4.5 Topics** — `docs/MQTT_TOPICS.md`, `scripts/mqtt_subscribe.py`
> detection (QoS 1, one per part), motor/score (QoS 0, 2 per s), status (QoS 1, retained + last-will "offline").
> Retained = a late subscriber gets the last state at once; last will = the broker announces "offline" if I die.

**4.6 PLC link** — `scripts/plc_watch.py`, `deploy/openplc/edge_tags.st`
> Modbus TCP: on each trigger coil 0 (%QX0.0) pulses 0.5 s and holding register 0 (%QW0) = part count. Laptop proof
> with a Modbus simulator: 7 triggers → 7 coil pulses, register 1→7. Modbus has no password → localhost + firewall.

**4.7 Threat model** — `docs/THREAT_MODEL.md` (device, network, application, physical; 5 mitigations applied).

**4.8 Reliability** — `scripts/drift_report.py`, `scripts/ota.py demo`, `deploy/*.service`
> *Drift:* PSI compares today's distribution with the baseline in 5 bins; small samples make PSI jumpy, so a feature
> must beat both 0.25 and 3× its sampling noise floor. Sharp frames: stable; hand-shake blur: "watch" on sharpness;
> failing lamp: DRIFT. *OTA:* hash check → install → health check (recall ≥ 0.9 on reference images) → rollback if it
> fails: v1 → v2 ok, broken v3 rolled back to v2, tampered bundle refused. *Auto-restart:* Docker
> `restart: unless-stopped` / systemd `Restart=always`. `docker exec edge sh -c 'kill -USR1 1'` makes the station
> crash (exit 70) from inside; it was back in 1.2 s (laptop, `evidence/M4/crash_restart_laptop.log`). Note: `docker kill`
> does NOT trigger a restart, because Docker treats it as a deliberate manual stop.

---

## M5 Complete System + Dashboard

**5.1 Inspection rig** — `docs/RIG.md`
> Fixed camera at 30–45°, plain matte base, a stop so every part sits the same way, diffused lamp. Same view every time
> means "good" always looks the same, so small differences are defects. The angle shows the side wall, which is what
> separates a closed box from a loose lid (my M1 wrong detection #7).

**5.2 Pass/fail station** — `src/edgevision/inspect.py`, `scripts/calibrate_inspection.py`, `scripts/passfail_test.py`
> Two layers: the detector says what is in view (closed enclosure / open body / lid); simple vision checks look at the
> enclosure crop: dark marks (the designed slot is excluded by its shape), solidity (a bite out of a corner makes the
> outline concave), rectangularity. Limits come from GOOD parts only, because defects are rare and varied.
> Stand-in result: 16/20, false-pass 0.30 — marks and lid-missing caught, chips not (camera angle varied in my phone
> video). I changed the method once after seeing the first result, so the second score is optimistic: the rig test is
> the honest number.

**5.3 Full chain** — `python scripts/station_sim.py --minutes 10 --mqtt --report`
> 10 min, 30.0 FPS (min 29.7), 0 errors, 171/172 parts tracked, 1858 MQTT messages received with 0 schema failures,
> part → reject p95 90 ms. What broke and the fix is listed in `evidence/M5/full_chain_laptop.json`
> (e.g. a 0.6 s blur in my simulator dropped it to 2.4 FPS: measure, find, fix).

**5.4 Dashboard** — `http://<device>:8000`
> FastAPI backend (REST + WebSocket + MJPEG) and a separate static page: the same API could feed a phone app.
> Live camera with boxes, big PASS/FAIL, headline metric, 3 KPIs (throughput, yield, median latency), motor card with
> score graph that turns red on an anomaly, parts feed with good/defective buttons. No CDN: works offline. Responsive.

**5.5 Product readiness** — `scripts/readiness_check.py` (7/7 static; `--pi` adds boot + offline checks)
> Auto-start: Docker enabled in systemd + `restart: unless-stopped` + `edge-compose.service`. Offline: broker, model,
> dashboard all local. Logs: RotatingFileHandler 1 MB × 5 + Docker json-file 5 MB × 3, so the SD card never fills.
> Healthcheck: container is "healthy" only while `/api/health` sees fresh frames.

**5.6 Headline metric** — dashboard tile + `GET /api/kpis`
> Parts classified correctly out of the parts I checked, with the false-pass rate next to it, because a defective part
> passing is the costly error.
