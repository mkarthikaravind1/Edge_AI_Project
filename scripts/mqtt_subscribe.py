"""M4.5: subscriber that prints every edge/# message (read-only user 'monitor', TLS) and checks it against the schema.

    python scripts/mqtt_subscribe.py                    # print until Ctrl+C
    python scripts/mqtt_subscribe.py --seconds 25 --save evidence/M4/mqtt_topics_sample.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from edgevision.comms.mqtt import make_client
from edgevision.config import load_config

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {  # minimal schema check: required keys per topic suffix (full schemas in docs/MQTT_TOPICS.md)
    "detection": {"device_id", "ts", "event", "count", "classes", "confidences", "boxes"},
    "motor/score": {"device_id", "ts", "score", "threshold", "alert"},
    "status": {"device_id", "state"},
}


def suffix(topic: str) -> str:
    return topic.split("/", 2)[2] if topic.count("/") >= 2 else topic


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--save", default=None)
    args = ap.parse_args()
    cfg = load_config()
    env = ROOT / "docker/.env"
    pw = dict(l.split("=", 1) for l in env.read_text().splitlines() if "=" in l).get("MQTT_MONITOR_PASSWORD") if env.exists() else None
    c = make_client(cfg, "subscriber", username="monitor", password=pw)
    msgs, counts, bad = [], Counter(), Counter()

    def on_message(cl, u, m):
        p = json.loads(m.payload)
        s = suffix(m.topic)
        missing = REQUIRED.get(s, set()) - set(p)
        counts[s] += 1
        if missing:
            bad[s] += 1
        msgs.append({"topic": m.topic, "retained": bool(m.retain), "payload": p, "schema_ok": not missing})
        if s != "motor/score" or counts[s] % 10 == 1:          # motor scores are 2 per second: print every 10th
            print(f"{m.topic:32s} {'OK ' if not missing else 'BAD'} {json.dumps(p)[:150]}")

    c.on_message = on_message
    c.on_connect = lambda cl, u, f, rc, p: (print(f"connected: {rc}"), cl.subscribe("edge/#", qos=1))
    c.connect(cfg["mqtt"]["host"], cfg["mqtt"].get("port", 8883))
    c.loop_start()
    try:
        time.sleep(args.seconds) if args.seconds else time.sleep(1e9)
    except KeyboardInterrupt:
        pass
    c.loop_stop()
    c.disconnect()
    print("received per topic:", dict(counts), "schema failures:", dict(bad))
    if args.save:
        out = ROOT / args.save
        out.parent.mkdir(parents=True, exist_ok=True)
        keep = {}
        for m in msgs:                                         # first 3 of each topic as samples
            keep.setdefault(suffix(m["topic"]), []).append(m) if len(keep.get(suffix(m["topic"]), [])) < 3 else None
        out.write_text(json.dumps({"received_per_topic": dict(counts), "schema_failures": dict(bad),
                                   "seconds": args.seconds, "samples": keep}, indent=2, default=str))


if __name__ == "__main__":
    main()
