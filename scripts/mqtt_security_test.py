"""M4.4: prove the broker refuses insecure clients and accepts password + TLS.

Cases
  1 anonymous over TLS                     -> must be refused (not authorised)
  2 right user, WRONG password, TLS         -> must be refused
  3 plain TCP on 1883 (no TLS)              -> must fail: no plain-text listener exists
  4 TLS with a CA that did not sign server  -> must fail: certificate not trusted (no man-in-the-middle)
  5 right user + password + TLS             -> accepted; publish + subscribe round trip works
  6 read-only user tries to publish         -> ACL drops it (message never arrives)

    python scripts/mqtt_security_test.py            (broker: docker compose -f docker/compose.yaml up -d mosquitto)
-> evidence/M4/mqtt_security.json + mqtt_security.log
"""

from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from edgevision.comms.mqtt import make_client
from edgevision.config import load_config
from edgevision.evidence import evidence_dir, write_json

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    p = ROOT / "docker/.env"
    return dict(l.split("=", 1) for l in p.read_text().splitlines() if "=" in l) if p.exists() else {}


def try_connect(c: mqtt.Client, host: str, port: int, timeout: float = 5.0) -> tuple[bool, str]:
    done, result = threading.Event(), {}

    def on_connect(cl, u, f, rc, p):
        result["rc"] = str(rc)
        result["ok"] = not rc.is_failure
        done.set()

    c.on_connect = on_connect
    try:
        c.connect(host, port, keepalive=10)
    except (ssl.SSLError, OSError) as e:
        return False, f"{type(e).__name__}: {e}"
    c.loop_start()
    done.wait(timeout)
    c.loop_stop()
    try:
        c.disconnect()
    except Exception:
        pass
    return result.get("ok", False), result.get("rc", "no CONNACK (connection dropped)")


def main() -> None:
    cfg = load_config()
    m = cfg["mqtt"]
    host, port = m["host"], m.get("port", 8883)
    e = env()
    pw, mon_pw = os.environ.get("MQTT_PASSWORD", e.get("MQTT_PASSWORD")), e.get("MQTT_MONITOR_PASSWORD")
    log_lines, cases = [], []

    def record(n, name, expect_ok, ok, detail):
        passed = ok == expect_ok
        cases.append({"case": n, "name": name, "expected": "accepted" if expect_ok else "refused",
                      "result": "accepted" if ok else "refused", "detail": detail, "pass": passed})
        line = f"[{'PASS' if passed else 'FAIL'}] {n}. {name}: {'accepted' if ok else 'refused'} ({detail})"
        log_lines.append(line)
        print(line)

    ok, d = try_connect(make_client(cfg, "t-anon", username="", password=None), host, port)
    record(1, "anonymous client over TLS", False, ok, d)
    ok, d = try_connect(make_client(cfg, "t-wrong", username="edge", password="wrong-password"), host, port)
    record(2, "user 'edge' with WRONG password over TLS", False, ok, d)

    plain = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="t-plain")
    plain.username_pw_set("edge", pw)
    ok, d = try_connect(plain, host, 1883)
    record(3, "correct password but PLAIN TCP :1883 (no TLS)", False, ok, d)

    with tempfile.TemporaryDirectory() as td:          # a self-made CA the broker's cert was NOT signed by
        subprocess.run([shutil.which("openssl") or "openssl", "req", "-x509", "-new", "-nodes", "-newkey", "rsa:2048",
                        "-days", "1", "-keyout", f"{td}/k", "-out", f"{td}/fake.crt", "-subj", "/CN=fake-ca"],
                       check=True, capture_output=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        fake = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="t-fakeca")
        fake.tls_set(ca_certs=f"{td}/fake.crt", cert_reqs=ssl.CERT_REQUIRED)
        fake.username_pw_set("edge", pw)
        ok, d = try_connect(fake, host, port)
    record(4, "TLS but trusting a different CA (impostor broker check)", False, ok, d)

    got = []
    sub = make_client(cfg, "t-sub", username="monitor", password=mon_pw)
    sub.on_message = lambda c, u, msg: got.append((msg.topic, msg.payload.decode()))
    sub.on_connect = lambda c, u, f, rc, p: c.subscribe("edge/#", qos=1)
    sub.connect(host, port)
    sub.loop_start()
    time.sleep(1.0)
    pub = make_client(cfg, "t-pub", username="edge", password=pw)
    connack = threading.Event()
    pub.on_connect = lambda c, u, f, rc, p: (d_.append(str(rc)), connack.set())
    d_: list[str] = []
    pub.connect(host, port)
    pub.loop_start()
    ok = connack.wait(5) and d_[0] == "Success"
    d = d_[0] if d_ else "no CONNACK"
    pub.publish(f"edge/{cfg['device_id']}/status", json.dumps({"test": "tls-ok", "ts": time.time()}), qos=1).wait_for_publish(3)
    time.sleep(1.0)
    roundtrip = any("tls-ok" in p for _, p in got)
    record(5, "user 'edge' + correct password + TLS (publish/subscribe round trip)", True, ok and roundtrip,
           f"{d}; round trip {'received' if roundtrip else 'NOT received'}")

    ro = make_client(cfg, "t-ro", username="monitor", password=mon_pw)
    ro.connect(host, port)
    ro.loop_start()
    time.sleep(0.5)
    ro.publish(f"edge/{cfg['device_id']}/status", json.dumps({"test": "acl-should-drop"}), qos=1).wait_for_publish(3)
    time.sleep(1.0)
    leaked = any("acl-should-drop" in p for _, p in got)
    record(6, "read-only user 'monitor' publishes (ACL)", False, leaked, "message dropped by ACL" if not leaked else "ACL leak!")
    for c in (sub, pub, ro):
        c.loop_stop()
        c.disconnect()

    res = {"broker": f"{host}:{port}", "listener": "TLS 1.2+ only, allow_anonymous false, password_file, acl_file",
           "cases": cases, "all_passed": all(c["pass"] for c in cases)}
    write_json("M4", "mqtt_security", res)
    (evidence_dir("M4") / "mqtt_security.log").write_text("\n".join(log_lines) + "\n")
    print("ALL PASSED" if res["all_passed"] else "SOME CASES FAILED")


if __name__ == "__main__":
    main()
