"""Station entry point: python -m edgevision.app   (what Docker / systemd start on the Pi)

    EDGE_TARGET=laptop python -m edgevision.app --source video --path data/raw/videos/clip1.mp4 --seconds 60
    EDGE_TARGET=pi     python -m edgevision.app            # runs until stopped (SIGTERM / Ctrl+C)

Builds every part from config/<target>.yaml through the HAL, so the same file runs on the laptop and the Pi.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import threading
from typing import Any

from .bus import EventBus
from .config import load_config, resolve
from .detect import make_detector
from .hal import make_actuator, make_camera, make_plc
from .ops.logs import setup_logging
from .runtime import StationRuntime

log = logging.getLogger("edgevision.app")


def build_runtime(cfg: dict[str, Any], bus: EventBus | None = None, quiet_actuators: bool = False,
                  realtime: bool = True) -> StationRuntime:
    cam_cfg = cfg["camera"]
    detector = make_detector(cfg["detector"], cfg["classes"])
    plc = None
    try:
        plc = make_plc(cfg.get("plc", {"type": "fake"}))
    except Exception:
        log.exception("PLC not reachable - continuing without it")
    inspector = None
    if cfg.get("inspection", {}).get("enabled"):
        from .inspect import make_inspector

        inspector = make_inspector(cfg)
    return StationRuntime(
        cfg, make_camera(cam_cfg, realtime=realtime), detector,
        reject=make_actuator(cfg["reject"], "reject", quiet_actuators),
        run_permit=make_actuator(cfg["run_permit"], "run_permit", quiet_actuators),
        plc=plc, bus=bus, inspector=inspector,
        camera_factory=lambda: make_camera(cam_cfg, realtime=realtime))


def attach_plugins(rt: StationRuntime, cfg: dict[str, Any]) -> list[Any]:
    """MQTT and the dashboard are optional subscribers of the bus."""
    plugins: list[Any] = []
    if cfg.get("mqtt", {}).get("enabled"):
        try:
            from .comms.mqtt import MqttBridge

            plugins.append(MqttBridge(cfg, rt.bus))
        except Exception:
            log.exception("MQTT disabled: broker not reachable")
    model_path = resolve(cfg.get("anomaly", {}).get("model_path", "models/anomaly.json"))
    if cfg.get("imu") and model_path.exists():
        try:
            from .hal import make_imu
            from .monitor import AnomalyModel, MotorMonitor

            mon = MotorMonitor(make_imu(cfg["imu"]), AnomalyModel.load(model_path), cfg, rt.bus, rt.device_id)
            mon.start()
            mon.close = mon.stop
            rt.motor = mon
            plugins.append(mon)
        except Exception:
            log.exception("motor monitor disabled: IMU not available")
    return plugins


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["webcam", "video", "picamera2"], default=None)
    ap.add_argument("--path", default=None)
    ap.add_argument("--seconds", type=float, default=None, help="stop after this long (default: run forever)")
    ap.add_argument("--dashboard", action="store_true", help="also serve the web dashboard")
    ap.add_argument("--inspect", action="store_true", help="enable the M5 pass/fail inspection")
    args = ap.parse_args()

    cfg = load_config()
    if args.source:
        cfg["camera"]["type"] = args.source
    if args.path:
        cfg["camera"]["path"] = args.path
    if args.inspect:
        cfg.setdefault("inspection", {})["enabled"] = True
    setup_logging(cfg)
    from .ops.ota import apply_current_release

    cfg = apply_current_release(cfg)             # OTA: use the model of deploy/releases/CURRENT if one is installed
    rt = build_runtime(cfg)
    plugins = attach_plugins(rt, cfg)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    if hasattr(signal, "SIGUSR1"):               # crash test: `docker exec edge sh -c 'kill -USR1 1'` / `systemctl kill -s USR1 edge-station`
        def crash(*_: Any) -> None:
            log.critical("FORCED CRASH TEST (SIGUSR1): exiting with code 70 without cleanup")
            logging.shutdown()
            os._exit(70)
        signal.signal(signal.SIGUSR1, crash)

    server = None
    if args.dashboard:
        from .dashboard.server import serve_in_thread

        server = serve_in_thread(rt, cfg)
    log.info("station starting: target=%s camera=%s backend=%s model=%s release=%s", cfg.get("target"),
             cfg["camera"]["type"], cfg["detector"]["backend"], cfg["detector"]["model"], cfg.get("release"))
    rt.start()
    stop.wait(args.seconds)
    rt.stop()
    for p in plugins:
        p.close()
    if server:
        server.should_exit = True
    log.info("station stopped: %s", json.dumps(rt.stats()))


if __name__ == "__main__":
    main()
