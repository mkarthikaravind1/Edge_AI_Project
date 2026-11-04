"""Load the YAML config for the current target (EDGE_TARGET=laptop|pi)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

def _find_root() -> Path:
    """Project folder (holds config/, models/, evidence/): EDGE_ROOT if set, else the source checkout
    (editable install), else the current directory (package installed into site-packages, e.g. in Docker)."""
    if os.environ.get("EDGE_ROOT"):
        return Path(os.environ["EDGE_ROOT"]).resolve()
    src_root = Path(__file__).resolve().parents[2]
    return src_root if (src_root / "config").is_dir() else Path.cwd()


ROOT = _find_root()


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
