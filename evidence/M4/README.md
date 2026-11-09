# M4 — Monitor and Connect: evidence index

Every M4 checklist item, the number that proves it, and the exact files. Files stay flat in this folder because the
scripts write them here; this page is the map.

**Where it ran:** 💻 = measured on the laptop · ⏳ Pi = Pi run pending ([PI_CHECKLIST § M4](../../docs/PI_CHECKLIST.md#m4--monitor-and-connect-on-the-pi)).
⚠️ The motor results (4.1–4.3) use clearly labelled **synthetic** IMU data until the MPU6050 runs are recorded.

| # | Criterion | Result | Evidence | Where |
|---|---|---|---|---|
| 4.1 | Sensor data | 8 normal + 3 fault runs (unbalance ×2, tap), 6-axis at 200 Hz, labelled CSVs | [data/imu/synthetic/](../../data/imu/synthetic/README.md) | ⚠️ synthetic, ⏳ Pi |
| 4.2 | Anomaly model | Normal-only z-score model on 72 features per 1 s window; live alert **1.0 s** after the fault | [anomaly_model.json](anomaly_model.json), [anomaly_scores.png](anomaly_scores.png), [live_alert.json](live_alert.json), model [anomaly.json](../../models/anomaly.json) | ⚠️ synthetic |
| 4.3 | False alarms | **1 false alarm in 5 unseen normal runs** (target ≤ 1); 3/3 faults detected | [false_alarms.json](false_alarms.json) | ⚠️ synthetic |
| 4.4 | Secure MQTT | TLS only, no anonymous, password file, ACL: **6/6** security cases pass | [mqtt_security.json](mqtt_security.json), [mqtt_security.log](mqtt_security.log), [mosquitto_broker.log](mosquitto_broker.log), [mosquitto.conf](../../docker/mosquitto/mosquitto.conf), [acl](../../docker/mosquitto/acl) | 💻, ⏳ Pi |
| 4.5 | Topics | 3 topics (detection, motor/score, status with retained + last will), 0 schema failures | [mqtt_topics_sample.json](mqtt_topics_sample.json), [MQTT_TOPICS](../../docs/MQTT_TOPICS.md) | 💻, ⏳ Pi |
| 4.6 | PLC link | Modbus TCP: 7 triggers → **7/7 coil pulses**, register counts 1→7 | [plc_link_laptop.json](plc_link_laptop.json), [plc_link_laptop.csv](plc_link_laptop.csv), OpenPLC program [edge_tags.st](../../deploy/openplc/edge_tags.st) | 💻 (Modbus simulator), ⏳ OpenPLC on Pi |
| 4.7 | Threat model | Device, network, application, physical; 5 mitigations applied | [THREAT_MODEL](../../docs/THREAT_MODEL.md) | — |
| 4.8 | Reliability | Drift report (PSI); OTA v1 → v2 ok, broken v3 **rolled back**, tampered bundle refused; restart after forced crash **1.2 s** | [drift_report.json](drift_report.json), [drift_report.png](drift_report.png), [ota.json](ota.json), [crash_restart_laptop.log](crash_restart_laptop.log), bundles [deploy/ota/bundles/](../../deploy/ota/bundles/) | 💻, ⏳ Pi |

## Code that produced it
| # | Script |
|---|---|
| 4.1 | [record_imu.py](../../scripts/record_imu.py), [gen_synthetic_imu.py](../../scripts/gen_synthetic_imu.py), [imu.py](../../src/edgevision/hal/imu.py) |
| 4.2 / 4.3 | [train_anomaly.py](../../scripts/train_anomaly.py), [motor_monitor.py](../../scripts/motor_monitor.py), [monitor/](../../src/edgevision/monitor/anomaly.py) |
| 4.4 / 4.5 | [mqtt_security_test.py](../../scripts/mqtt_security_test.py), [mqtt_subscribe.py](../../scripts/mqtt_subscribe.py), [mqtt.py](../../src/edgevision/comms/mqtt.py) |
| 4.6 | [plc_watch.py](../../scripts/plc_watch.py), [plc_sim.py](../../scripts/plc_sim.py), [plc.py](../../src/edgevision/hal/plc.py) |
| 4.8 | [drift_report.py](../../scripts/drift_report.py), [ota.py](../../scripts/ota.py), [ops/ota.py](../../src/edgevision/ops/ota.py) |

More: [VIVA_NOTES § M4](../../docs/VIVA_NOTES.md#m4-monitor-and-connect) · all numbers: [RESULTS § M4](../../docs/RESULTS.md#m4)
