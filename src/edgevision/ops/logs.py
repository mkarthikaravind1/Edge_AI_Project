"""Rotating log files: the device can run for weeks without filling the SD card."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Any

from ..config import resolve


def setup_logging(cfg: dict[str, Any], name: str = "edgevision") -> logging.Logger:
    c = cfg.get("logging", {})
    d = resolve(c.get("dir", "logs"))
    d.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(threadName)-9s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = RotatingFileHandler(d / f"{name}.log", maxBytes=c.get("max_bytes", 1_000_000),
                             backupCount=c.get("backups", 5), encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    return logging.getLogger(name)
