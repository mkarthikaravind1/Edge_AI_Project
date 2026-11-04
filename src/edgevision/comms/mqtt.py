"""MQTT over TLS: forwards bus events to the broker.

Topics (schemas in docs/MQTT_TOPICS.md):
  edge/<device_id>/detection     every trigger (decision rule fired)       QoS 1
  edge/<device_id>/motor/score   every motor window (0.5 s)                QoS 0
  edge/<device_id>/status        once per second, retained; LWT "offline"  QoS 1
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
from typing import Any

import paho.mqtt.client as mqtt

from ..bus import EventBus
from ..config import resolve

log = logging.getLogger(__name__)


def make_client(cfg: dict[str, Any], client_id: str, username: str | None = None,
                password: str | None = None) -> mqtt.Client:
    m = cfg["mqtt"]
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311)
    if m.get("tls", True):
        c.tls_set(ca_certs=str(resolve(m["ca"])), cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    user = username if username is not None else m.get("username")
    pw = password if password is not None else os.environ.get(m.get("password_env", "MQTT_PASSWORD"))
    if pw is None and user:                    # laptop runs outside Docker: read the git-ignored docker/.env
        env = resolve("docker/.env")
        if env.exists():
            pw = dict(l.split("=", 1) for l in env.read_text().splitlines() if "=" in l).get(m.get("password_env", "MQTT_PASSWORD"))
    if user:
        c.username_pw_set(user, pw)
    return c


class MqttBridge:
    def __init__(self, cfg: dict[str, Any], bus: EventBus) -> None:
        m = cfg["mqtt"]
        self.dev = cfg.get("device_id", "edge")
        self.base = f"edge/{self.dev}"
        self.c = make_client(cfg, f"{self.dev}-station")
        self.c.will_set(f"{self.base}/status", json.dumps({"device_id": self.dev, "state": "offline"}), qos=1, retain=True)
        self.c.on_connect = lambda c, u, f, rc, p: log.info("MQTT connected rc=%s", rc)
        self.c.on_disconnect = lambda c, u, f, rc, p: log.warning("MQTT disconnected rc=%s", rc)
        self.c.reconnect_delay_set(1, 30)
        self.c.connect_async(m["host"], m.get("port", 8883), keepalive=30)
        self.c.loop_start()
        self.sent = 0
        bus.subscribe("decision", self._on_decision)
        bus.subscribe("motor", self._on_motor)
        bus.subscribe("status", self._on_status)

    def _pub(self, topic: str, payload: dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        if self.c.is_connected():
            self.c.publish(f"{self.base}/{topic}", json.dumps(payload, default=str), qos=qos, retain=retain)
            self.sent += 1

    def _on_decision(self, _: str, p: dict[str, Any]) -> None:
        if p.get("event") == "trigger":
            dets = p.get("detections", [])
            self._pub("detection", {"device_id": self.dev, "ts": time.time(), "event": "trigger",
                                    "count": p.get("count"), "classes": [d["name"] for d in dets],
                                    "confidences": [d["conf"] for d in dets], "boxes": [d["box"] for d in dets],
                                    "verdict": (p.get("verdict") or {}).get("verdict"),
                                    "latency_ms": p.get("frame_to_cmd_ms")}, qos=1)
        elif p.get("event") in ("safe_state", "recovered"):
            self._pub("status", {"device_id": self.dev, "ts": time.time(), "state": p["event"],
                                 "reason": p.get("reason")}, qos=1, retain=True)

    def _on_motor(self, _: str, p: dict[str, Any]) -> None:
        self._pub("motor/score", {"device_id": self.dev, "ts": p.get("t", time.time()), "score": p["score"],
                                  "threshold": p["threshold"], "alert": p["alert"]})

    def _on_status(self, _: str, p: dict[str, Any]) -> None:
        self._pub("status", {"ts": time.time(), **p}, qos=1, retain=True)

    def close(self) -> None:
        self._pub("status", {"device_id": self.dev, "ts": time.time(), "state": "offline"}, qos=1, retain=True)
        time.sleep(0.2)
        self.c.loop_stop()
        self.c.disconnect()
