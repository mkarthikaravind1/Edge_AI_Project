# M4 — Monitor and Connect: evidence

One section per task on the marking sheet. Each section shows what the task asks for, what I measured so far, the
files, and a place for the **group run on the Pi** (photos in this folder, videos as Drive/YouTube links).

**Where it ran:** 💻 = measured on my laptop (every json records its host) · 👥 Pi = group run on the shared Pi rig,
media to add. ⚠️ The motor results (4.1–4.3) so far use clearly labelled **synthetic** IMU data; real MPU6050 runs
replace them. Pi commands: [PI_CHECKLIST § M4](../../docs/PI_CHECKLIST.md#m4--monitor-and-connect-on-the-pi).

**Group media rule:** every photo/video from the group session is labelled *"group run on the shared Pi rig — my part:
… — filmed by …"*. My own measured numbers are listed separately from the group media.

| Task | Max | Measured so far | Section |
|---|---|---|---|
| Sensor data | 3 | 8 normal + 3 fault runs, 6 axes at 200 Hz (synthetic) | [4.1](#41-sensor-data) |
| Anomaly model | 4 | trained on normal only; live alert 1.0 s after the fault | [4.2](#42-anomaly-model) |
| False alarms | 2 | 1 false alarm in 5 unseen normal runs; threshold = 99.5th percentile | [4.3](#43-false-alarms) |
| Secure MQTT | 3 | 6/6 security cases (no-password refused, password + TLS works) | [4.4](#44-secure-mqtt) |
| Topics | 2 | detection, motor score, status received; 0 schema failures | [4.5](#45-topics) |
| PLC link | 2 | 7 triggers → 7 coil pulses, register 1 → 7 | [4.6](#46-plc-link) |
| Threat model | 1 | 1 threat per level (4 levels), 5 mitigations applied | [4.7](#47-threat-model) |
| Reliability | 3 | drift report; OTA v1 → v2, broken v3 rolled back; restart after crash 1.2 s | [4.8](#48-reliability) |

---

## 4.1 Sensor data

**Asked:** wire/read the MPU6050 and show labelled normal and fault CSV runs (3 each).

- MPU6050 on I²C-1 (address 0x68): 3-axis accelerometer + 3-axis gyro at **200 Hz**, 30 s per run, saved as labelled CSVs.
  Wiring table: [PI_CHECKLIST § 4.1](../../docs/PI_CHECKLIST.md#41-mpu6050-wiring-pi-off-while-wiring).
- ⚠️ Runs so far (synthetic, labelled as such — [data/imu/synthetic/README.md](../../data/imu/synthetic/README.md)):
  **8 normal** (`normal_1` … `normal_8`) and **3 fault** runs: [fault_unbalance_1](../../data/imu/synthetic/fault_unbalance_1.csv),
  [fault_unbalance_2](../../data/imu/synthetic/fault_unbalance_2.csv), [fault_tap_1](../../data/imu/synthetic/fault_tap_1.csv).
- Code: [scripts/record_imu.py](../../scripts/record_imu.py) (real sensor), [scripts/gen_synthetic_imu.py](../../scripts/gen_synthetic_imu.py),
  [src/edgevision/hal/imu.py](../../src/edgevision/hal/imu.py).

👥 **Group run on the Pi** — photo of the MPU6050 on the motor, real normal and fault CSVs (`data/imu/real/`): _to add_.

## 4.2 Anomaly model

**Asked:** train on normal data only and show the live alert when I inject the fault.

- Each 1 s window (step 0.5 s) → **36 features** = 6 axes × (RMS, peak, FFT energy in 0–5 / 5–20 / 20–50 / 50–100 Hz).
- Trained on **normal runs only** (`normal_1`, `normal_2`, 118 windows): learn each feature's mean and spread;
  score = distance from normal in standard deviations. Alert after 2 windows in a row above the threshold.
- Fault runs: **3/3 detected** (first alert 1.5–2.0 s into the run) — [anomaly_model.json](anomaly_model.json),
  scores plot [anomaly_scores.png](anomaly_scores.png).
- ⚠️ Live alert (synthetic replay at real time): fault injected at 10.0 s → **alert at 11.0 s (1.0 s)**, 0 alerts before
  ([live_alert.json](live_alert.json)). Model file: [models/anomaly.json](../../models/anomaly.json).
- Code: [scripts/train_anomaly.py](../../scripts/train_anomaly.py), [scripts/motor_monitor.py](../../scripts/motor_monitor.py),
  [src/edgevision/monitor/](../../src/edgevision/monitor/anomaly.py).

![anomaly scores](anomaly_scores.png)

👥 **Group run on the Pi** — video of the dashboard motor card turning red when the fault is injected: _to add_.

## 4.3 False alarms

**Asked:** count false alarms over 5 normal runs and explain my threshold.

- Threshold = **99.5th percentile** of scores on `normal_3`, a normal run used **neither for training nor for testing**
  (a training percentile would be too low, because the model always looks best on its own training data) → **9.198**.
- ⚠️ Counted on 5 more unseen normal runs (`normal_4` … `normal_8`, 2.5 min): **1 false alarm** (in `normal_7`), target ≤ 1 ✅
  ([false_alarms.json](false_alarms.json)).
- Trade-off: a higher percentile gives fewer false alarms but later or missed faults.

👥 **Group run on the Pi** — the same count on real normal runs: _to add_.

## 4.4 Secure MQTT

**Asked:** show the broker refuses no-password and works with password + TLS.

💻 Mosquitto in Docker, TLS-only listener on 8883 (no plain 1883 at all), no anonymous users, password file, per-user ACL
([mqtt_security.json](mqtt_security.json), log [mqtt_security.log](mqtt_security.log), broker log [mosquitto_broker.log](mosquitto_broker.log)) — **6/6 pass**:

| Case | Expected | Result |
|---|---|---|
| anonymous client over TLS | refused | refused |
| wrong password over TLS | refused | refused |
| correct password but plain TCP :1883 (no TLS) | refused | refused |
| TLS but trusting a different CA (impostor broker) | refused | refused |
| correct password + TLS (publish/subscribe round trip) | accepted | accepted |
| read-only user publishes (ACL) | refused | refused |

Config: [mosquitto.conf](../../docker/mosquitto/mosquitto.conf), [acl](../../docker/mosquitto/acl),
[make_certs.sh](../../docker/mosquitto/make_certs.sh). Test: [scripts/mqtt_security_test.py](../../scripts/mqtt_security_test.py).

👥 **Group run on the Pi** — screenshot of the refused / accepted connections on the Pi broker: _to add_.

## 4.5 Topics

**Asked:** publish detection and motor score and show them on a subscriber.

💻 Subscriber for 120 s ([mqtt_topics_sample.json](mqtt_topics_sample.json)), **0 schema failures**:

| Topic | QoS | Received | Meaning |
|---|---|---|---|
| `edge/<device>/detection` | 1 | 2 | one message per part (class, confidence, box, verdict, latency) |
| `edge/<device>/motor/score` | 0 | 50 | anomaly score, 2 per second |
| `edge/<device>/status` | 1, retained + last will "offline" | 28 | health, FPS, outputs |

Topic design: [docs/MQTT_TOPICS.md](../../docs/MQTT_TOPICS.md). Code: [src/edgevision/comms/mqtt.py](../../src/edgevision/comms/mqtt.py),
subscriber [scripts/mqtt_subscribe.py](../../scripts/mqtt_subscribe.py).

👥 **Group run on the Pi** — screenshot of the subscriber printing detection and motor messages: _to add_.

## 4.6 PLC link

**Asked:** show the PLC tag change when an object is detected.

- Modbus TCP: on each trigger coil 0 (**%QX0.0**) pulses 0.5 s and holding register 0 (**%QW0**) = part count.
- 💻 Laptop with a Modbus simulator, 70 s: **7 triggers → 7 coil pulses, register 1 → 7**
  ([plc_link_laptop.json](plc_link_laptop.json), timeline [plc_link_laptop.csv](plc_link_laptop.csv)).
- OpenPLC program for the Pi: [deploy/openplc/edge_tags.st](../../deploy/openplc/edge_tags.st).
  Code: [scripts/plc_watch.py](../../scripts/plc_watch.py), [src/edgevision/hal/plc.py](../../src/edgevision/hal/plc.py).

👥 **Group run on the Pi** — screenshot/video of the OpenPLC Monitoring page: %QX0.0 blinks and %QW0 counts when a part is shown: _to add_.

## 4.7 Threat model

**Asked:** show one threat per level and 2 mitigations applied.

Full table: [docs/THREAT_MODEL.md](../../docs/THREAT_MODEL.md).

| Level | Threat | Mitigation applied | Proof |
|---|---|---|---|
| Device | stolen SD card / shell access reads the broker password | secrets only in git-ignored `.env`, broker keeps salted hashes | `.gitignore` |
| Network | sniffing or spoofing MQTT | TLS only, no anonymous, passwords, ACL, broker certificate check | [4.4](#44-secure-mqtt) 6/6 |
| Application | malicious or broken model update | hash check, health check, automatic rollback | [4.8](#48-reliability) |
| Physical / data | camera covered or unplugged, failing lamp | safe state stops the line; drift report | [M3 § 3.4](../M3/README.md#34-actuator-fires), [4.8](#48-reliability) |

**5 mitigations applied** (≥ 2 required); known gaps (Modbus has no password, dashboard has no login) are listed with their next step.

## 4.8 Reliability

**Asked:** show the drift report, OTA v1 to v2 with rollback, and auto-restart after a forced crash.

- **Drift report** (PSI on brightness, contrast, sharpness, confidence, boxes vs the dataset baseline;
  [drift_report.json](drift_report.json)): sharp frames → all **stable**; hand-shake blur → sharpness **watch**;
  simulated failing lamp → **DRIFT** on 4 of 5.
- **OTA** ([ota.json](ota.json)): install v1 ✅ → upgrade to **v2** ✅ → broken **v3 rolled back to v2** ✅ →
  tampered v2 bundle **refused** (hash mismatch) ✅. Bundles: [deploy/ota/bundles/](../../deploy/ota/bundles/).
- **Auto-restart** ([crash_restart_laptop.log](crash_restart_laptop.log)): forced crash inside the container
  (exit code 70) → Docker restarted it, station back **1.2 s** later (restart count 0 → 1).
- Code: [scripts/drift_report.py](../../scripts/drift_report.py), [scripts/ota.py](../../scripts/ota.py),
  [src/edgevision/ops/ota.py](../../src/edgevision/ops/ota.py).

![drift report](drift_report.png)

👥 **Group run on the Pi** — video of the forced crash and automatic restart, and the OTA rollback on the Pi: _to add_.

---
More: [VIVA_NOTES § M4](../../docs/VIVA_NOTES.md#m4-monitor-and-connect) · all numbers: [RESULTS § M4](../../docs/RESULTS.md#m4)
