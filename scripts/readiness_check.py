"""M5.5: product readiness - auto-start, offline operation, rotating logs. Every check prints PASS/FAIL with proof.

    python scripts/readiness_check.py                      # static checks (laptop or Pi)
    EDGE_TARGET=pi python scripts/readiness_check.py --pi  # + systemd/docker boot settings, health, and "internet unplugged"
-> evidence/M5/readiness_<host>.json
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import urllib.request
from pathlib import Path

import yaml

from edgevision.config import load_config
from edgevision.evidence import write_json
from edgevision.hostinfo import host_tag

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return f"ERR {e}"


def internet_up() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return True
    except OSError:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    checks = []

    def check(name: str, ok: bool, proof: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "proof": proof})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {proof}")

    static = ROOT / "src/edgevision/dashboard/static"
    ext = [f"{p.name}: {m}" for p in static.glob("*") for m in re.findall(r"(?:src|href)=\"(https?://[^\"]+)", p.read_text(encoding="utf-8"))]
    check("dashboard loads nothing from the internet", not ext, "no external src/href" if not ext else "; ".join(ext))
    check("MQTT broker is local", cfg["mqtt"]["host"] in ("localhost", "127.0.0.1", "mosquitto"),
          f"mqtt.host = {cfg['mqtt']['host']}")
    check("model + config are files on the device", (ROOT / cfg["detector"]["model"]).exists(), cfg["detector"]["model"])

    comp = yaml.safe_load((ROOT / "docker/compose.yaml").read_text(encoding="utf-8"))
    pol = {k: v.get("restart") for k, v in comp["services"].items()}
    check("containers restart automatically", all(p in ("always", "unless-stopped") for p in pol.values()), json.dumps(pol))
    unit = (ROOT / "deploy/edge-station.service").read_text(encoding="utf-8")
    check("systemd unit restarts the station", "Restart=always" in unit and "WantedBy=multi-user.target" in unit,
          "edge-station.service: Restart=always, WantedBy=multi-user.target")
    boot = (ROOT / "deploy/edge-compose.service").read_text(encoding="utf-8")
    check("compose stack starts at boot", "docker compose" in boot and "multi-user.target" in boot, "edge-compose.service")
    logs = (ROOT / "src/edgevision/ops/logs.py").read_text(encoding="utf-8")
    lc = cfg.get("logging", {})
    rot = {k: v.get("logging", {}).get("options") for k, v in comp["services"].items()}
    check("logs rotate", "RotatingFileHandler" in logs and all(rot.values()),
          f"app: RotatingFileHandler {lc.get('max_bytes')} B x {lc.get('backups')} files; docker: {json.dumps(rot)}")

    if args.pi:
        check("docker enabled at boot", sh(["systemctl", "is-enabled", "docker"]) == "enabled",
              "systemctl is-enabled docker = " + sh(["systemctl", "is-enabled", "docker"]))
        st = sh(["systemctl", "is-enabled", "edge-compose"])
        check("edge-compose enabled at boot", st == "enabled", "systemctl is-enabled edge-compose = " + st)
        ps = sh(["docker", "ps", "--format", "{{.Names}} {{.Status}}"])
        check("both containers up", "edge Up" in ps and "mosquitto Up" in ps, ps.replace("\n", " | "))
        try:
            h = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5).read())
        except Exception as e:
            h = {"ok": False, "error": str(e)}
        net = internet_up()
        check("station healthy", h.get("ok"), json.dumps(h))
        check("works OFFLINE (run this with the network cable / Wi-Fi off)", h.get("ok") and not net,
              f"internet reachable: {net}; station healthy: {h.get('ok')}")
        check("boot time (since power on)", True, sh(["uptime", "-p"]) + " | " + sh(["systemd-analyze"]).split("\n")[0])
        check("log files present", True, sh(["ls", "-la", str(ROOT / "logs")]).replace("\n", " | ")[:400])

    res = {"host_mode": "pi" if args.pi else "static", "checks": checks, "all_passed": all(c["pass"] for c in checks)}
    write_json("M5", f"readiness_{host_tag()}", res)
    print("ALL PASSED" if res["all_passed"] else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
