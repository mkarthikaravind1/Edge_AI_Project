"""Every number goes to evidence/Mx/<task>.json together with host info."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .config import ROOT
from .hostinfo import host_info


def evidence_dir(milestone: str) -> Path:
    d = ROOT / "evidence" / milestone
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(milestone: str, task: str, data: dict[str, Any], with_host: bool = True) -> Path:
    payload = {"task": task, **({"host": host_info()} if with_host else {}), **data}
    path = evidence_dir(milestone) / f"{task}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def write_csv(milestone: str, task: str, rows: Iterable[dict[str, Any]]) -> Path:
    rows = list(rows)
    path = evidence_dir(milestone) / f"{task}.csv"
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return path
