"""Load the YAML config for the current target (EDGE_TARGET=laptop|pi)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(target: str | None = None, path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        target = target or os.environ.get("EDGE_TARGET", "laptop")
        path = ROOT / "config" / f"{target}.yaml"
    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)
    return cfg


def resolve(p: str | Path) -> Path:
    """Paths in the config are relative to the repo root."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
