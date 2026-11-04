# MQTT topics (M4.5)

Broker: Mosquitto 2.0.20 in Docker, **TLS only on 8883**, no anonymous clients, password file + ACL
(`docker/mosquitto/`). Publisher: `src/edgevision/comms/mqtt.py` (user `edge`, may write `edge/#`).
Subscriber: `scripts/mqtt_subscribe.py` (user `monitor`, read-only). `<device_id>` = `pi-karthik` / `laptop-karthik`.

| Topic | When | QoS | Retained |
|---|---|---|---|
| `edge/<device_id>/detection` | every time the decision rule fires (one per part) | 1 | no |
| `edge/<device_id>/motor/score` | every motor window (every 0.5 s) | 0 | no |
| `edge/<device_id>/status` | once per second + on safe state / recovery; **last will** = `offline` | 1 | yes |

QoS 1 for detections and status: they must not be lost. QoS 0 for motor scores: the next one arrives 0.5 s later.
Status is retained, so a dashboard that connects late immediately sees the last state; the last will makes the broker
publish `offline` by itself if the station dies without saying goodbye.

## JSON schemas

### `edge/<device_id>/detection`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["device_id", "ts", "event", "count", "classes", "confidences", "boxes"],
  "properties": {
    "device_id":   {"type": "string"},
    "ts":          {"type": "number", "description": "unix time, s"},
    "event":       {"const": "trigger"},
    "count":       {"type": "integer", "description": "triggers since start"},
    "classes":     {"type": "array", "items": {"enum": ["enclosure", "body", "lid"]}},
    "confidences": {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1}},
    "boxes":       {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                    "description": "x1, y1, x2, y2 in image pixels"},
    "verdict":     {"enum": ["PASS", "FAIL", "NONE", null], "description": "M5 inspection result"},
    "latency_ms":  {"type": "number", "description": "frame capture -> actuator command"}
  }
}
```
Example (captured, `evidence/M4/mqtt_topics_sample.json`):
`{"device_id": "laptop-karthik", "event": "trigger", "count": 1, "classes": ["enclosure"], "confidences": [0.9693], ...}`

### `edge/<device_id>/motor/score`
```json
{
  "type": "object",
  "required": ["device_id", "ts", "score", "threshold", "alert"],
  "properties": {
    "device_id": {"type": "string"},
    "ts":        {"type": "number"},
    "score":     {"type": "number", "minimum": 0, "description": "anomaly score of the last 1 s window"},
    "threshold": {"type": "number", "description": "99.5th percentile of a held-out normal run"},
    "alert":     {"type": "boolean", "description": "true after 2 windows in a row above threshold"}
  }
}
```

### `edge/<device_id>/status`
```json
{
  "type": "object",
  "required": ["device_id", "state"],
  "properties": {
    "device_id":   {"type": "string"},
    "ts":          {"type": "number"},
    "state":       {"enum": ["starting", "running", "SAFE_STATE", "safe_state", "recovered", "stopped", "offline"]},
    "uptime_s":    {"type": "number"},
    "frames":      {"type": "integer"},
    "fps":         {"type": "number"},
    "triggers":    {"type": "integer"},
    "safe_events": {"type": "integer"},
    "errors":      {"type": "object"},
    "run_permit":  {"type": "boolean"},
    "reject":      {"type": "boolean"},
    "class_counts":{"type": "object"}
  }
}
```

## Measured (laptop, real broker in Docker)
- Security: 6/6 cases pass (`evidence/M4/mqtt_security.json`, `mqtt_security.log`, broker log `mosquitto_broker.log`).
- Topics: station on the video + fault IMU replay for 25 s → subscriber received status 28, detection 2,
  motor/score 50, **0 schema failures** (`evidence/M4/mqtt_topics_sample.json`).
