"""Over-the-air model updates with integrity check, health check and automatic rollback.

Bundle  = edge-<version>.tar.gz  containing  manifest.json + model file (+ overlay.yaml with config changes)
          edge-<version>.tar.gz.sha256  = SHA-256 of the whole bundle (published next to it)
Install = 1 bundle hash matches .sha256          (tampered / truncated download -> rejected, nothing changes)
          2 every file hash matches manifest.json
          3 unpack to deploy/releases/<version>/, point deploy/releases/CURRENT at it (old one kept as PREVIOUS)
          4 health check with the new release; FAIL -> point CURRENT back to PREVIOUS (automatic rollback)
The station reads CURRENT at start-up (apply_current_release), so a restart picks up the new model.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import shutil
import tarfile
import time
from pathlib import Path
from typing import Any

import yaml

from ..config import ROOT

log = logging.getLogger(__name__)
RELEASES = ROOT / "deploy/releases"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_bundle(version: str, model: Path, out_dir: Path, overlay: dict[str, Any] | None = None,
                 notes: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / f".build-{version}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    shutil.copy2(model, work / model.name)
    files = [model.name]
    if overlay:
        (work / "overlay.yaml").write_text(yaml.safe_dump(overlay))
        files.append("overlay.yaml")
    manifest = {"version": version, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model.name,
                "notes": notes, "files": {f: sha256(work / f) for f in files}}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
    bundle = out_dir / f"edge-{version}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        for f in ["manifest.json", *files]:
            tar.add(work / f, arcname=f)
    shutil.rmtree(work)
    (out_dir / f"{bundle.name}.sha256").write_text(f"{sha256(bundle)}  {bundle.name}\n")
    return bundle


def _pointer(name: str) -> str | None:
    p = RELEASES / name
    return p.read_text().strip() if p.exists() else None


def _set_pointer(name: str, value: str | None) -> None:
    RELEASES.mkdir(parents=True, exist_ok=True)
    p = RELEASES / name
    if value is None:
        p.unlink(missing_ok=True)
    else:
        p.write_text(value + "\n")


def current_version() -> str | None:
    return _pointer("CURRENT")


def apply_current_release(cfg: dict[str, Any], version: str | None = None) -> dict[str, Any]:
    """Return a config that uses the model (and overlay) of the given / CURRENT release, if any."""
    v = version or current_version()
    if not v:
        return cfg
    d = RELEASES / v
    man = json.loads((d / "manifest.json").read_text())
    out = copy.deepcopy(cfg)
    out["detector"]["model"] = str((d / man["model"]).relative_to(ROOT))
    # a release decides the runtime too: a .tflite model must not be handed to ONNX Runtime (or the reverse)
    backend = {".tflite": "tflite", ".onnx": "onnx", ".pt": "ultralytics"}.get(Path(man["model"]).suffix)
    if backend:
        out["detector"]["backend"] = backend
    if (d / "overlay.yaml").exists():
        for section, values in (yaml.safe_load((d / "overlay.yaml").read_text()) or {}).items():
            out.setdefault(section, {}).update(values)
    out["release"] = v
    return out


def install(bundle: Path, cfg: dict[str, Any], health) -> dict[str, Any]:
    """health: callable(cfg) -> {"ok": bool, ...}. Returns a report; never leaves a broken CURRENT."""
    rep: dict[str, Any] = {"bundle": bundle.name, "previous": current_version(), "steps": []}

    def step(name: str, ok: bool, **kw: Any) -> bool:
        rep["steps"].append({"step": name, "ok": ok, **kw})
        log.info("OTA %s: %s %s", name, "ok" if ok else "FAILED", kw or "")
        return ok

    sha_file = bundle.with_name(bundle.name + ".sha256")
    expected = sha_file.read_text().split()[0] if sha_file.exists() else None
    actual = sha256(bundle)
    if not step("bundle_sha256", expected == actual, expected=expected, actual=actual):
        rep["result"] = "rejected: bundle hash mismatch (tampered or corrupted download)"
        return rep

    with tarfile.open(bundle) as tar:
        man = json.loads(tar.extractfile("manifest.json").read())
        version = man["version"]
        dest = RELEASES / version
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        for m in tar.getmembers():
            if m.name not in ("manifest.json", *man["files"]) or not m.isfile():
                continue                                   # never unpack anything the manifest does not list
            (dest / m.name).write_bytes(tar.extractfile(m).read())
        (dest / "manifest.json").write_text(json.dumps(man, indent=2))
    rep["version"] = version
    bad = [f for f, h in man["files"].items() if sha256(dest / f) != h]
    if not step("file_hashes", not bad, mismatched=bad):
        shutil.rmtree(dest, ignore_errors=True)
        rep["result"] = "rejected: file hash mismatch"
        return rep

    prev = current_version()
    _set_pointer("PREVIOUS", prev)
    _set_pointer("CURRENT", version)
    step("switch", True, current=version, previous=prev)

    h = health(apply_current_release(cfg, version))
    rep["health"] = h
    if step("health_check", bool(h.get("ok")), reason=h.get("reason")):
        rep["result"] = f"installed {version}"
        return rep
    _set_pointer("CURRENT", prev)
    step("rollback", True, current=prev)
    rep["result"] = f"rolled back to {prev}: {version} failed the health check ({h.get('reason')})"
    return rep


def rollback() -> str | None:
    prev = _pointer("PREVIOUS")
    if prev:
        _set_pointer("CURRENT", prev)
    return prev
