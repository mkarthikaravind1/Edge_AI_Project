"""Describe the machine a measurement was taken on, so laptop numbers are never mistaken for Pi numbers."""

from __future__ import annotations

import platform
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


def _cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        text = cpuinfo.read_text(errors="ignore")
        for key in ("model name", "Model", "Hardware"):
            for line in text.splitlines():
                if line.startswith(key):
                    return line.split(":", 1)[1].strip()
    if platform.system() == "Windows":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=10,
            )
            if out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


def device_type() -> str:
    model = Path("/proc/device-tree/model")
    if model.exists():
        text = model.read_text(errors="ignore").strip("\x00 \n")
        if "Raspberry Pi" in text:
            return text
    return "laptop"


def soc_temperature_c() -> float | None:
    """Pi: vcgencmd, else Linux thermal zone. Windows laptops usually expose nothing -> None."""
    try:
        out = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2)
        if out.returncode == 0 and "temp=" in out.stdout:
            return float(out.stdout.split("=")[1].split("'")[0])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    zone = Path("/sys/class/thermal/thermal_zone0/temp")
    if zone.exists():
        try:
            return int(zone.read_text().strip()) / 1000.0
        except ValueError:
            return None
    return None


def gpu_utilisation() -> float | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0:
            return float(out.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return None


def host_info() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "device_type": device_type(),
        "cpu_model": _cpu_model(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def host_tag() -> str:
    return "pi" if device_type() != "laptop" else "laptop"
