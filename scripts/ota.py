"""M4.8: OTA model update v1 -> v2, a broken v3 that is rolled back automatically, and a tampered bundle that is refused.

    python scripts/ota.py build                     # makes deploy/ota/bundles/edge-v1|v2|v3-broken (+ .sha256)
    python scripts/ota.py install deploy/ota/bundles/edge-v2.tar.gz
    python scripts/ota.py status | rollback
    python scripts/ota.py demo                      # the full story -> evidence/M4/ota.json + logs/ota.log
On the Pi (Docker): docker exec edge python scripts/ota.py install /app/deploy/ota/bundles/edge-v2.tar.gz
                    docker restart edge             # the station loads CURRENT at start-up
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from edgevision.config import ROOT, load_config
from edgevision.evidence import write_json
from edgevision.ops import ota
from edgevision.ops.health import health_check
from edgevision.ops.logs import setup_logging

BUNDLES = ROOT / "deploy/ota/bundles"


def build() -> None:
    ota.build_bundle("v1", ROOT / "models/best_int8.tflite", BUNDLES,
                     notes="first release: TFLite INT8 (float I/O)")
    ota.build_bundle("v2", ROOT / "models/best_int8_full.tflite", BUNDLES, overlay={"detector": {"threads": 4}},
                     notes="full-integer INT8 (Edge-TPU ready, faster input path)")
    broken = ROOT / "runs/broken_model.tflite"                  # a release that was packaged wrongly
    broken.parent.mkdir(exist_ok=True)
    broken.write_bytes((ROOT / "models/best_int8.tflite").read_bytes()[:200_000])
    ota.build_bundle("v3-broken", broken, BUNDLES, notes="DEMO: truncated model file, must be rolled back")
    for p in sorted(BUNDLES.glob("*.tar.gz")):
        print(p.name, round(p.stat().st_size / 1e6, 2), "MB")


def install(path: str) -> dict:
    cfg = load_config()
    rep = ota.install(Path(path), cfg, health_check)
    print(json.dumps({k: v for k, v in rep.items() if k != "health"}, indent=1))
    return rep


def demo() -> None:
    shutil.rmtree(ota.RELEASES, ignore_errors=True)
    build()
    story = []
    for name in ("edge-v1.tar.gz", "edge-v2.tar.gz", "edge-v3-broken.tar.gz"):
        rep = install(str(BUNDLES / name))
        story.append({**rep, "current_after": ota.current_version()})
    tampered = ROOT / "runs/edge-v2-tampered.tar.gz"             # attacker swaps bytes after publication
    data = bytearray((BUNDLES / "edge-v2.tar.gz").read_bytes())
    data[len(data) // 2] ^= 0xFF
    tampered.write_bytes(bytes(data))
    shutil.copy2(BUNDLES / "edge-v2.tar.gz.sha256", tampered.with_name(tampered.name + ".sha256"))
    (tampered.with_name(tampered.name + ".sha256")).write_text(
        (BUNDLES / "edge-v2.tar.gz.sha256").read_text().replace("edge-v2.tar.gz", tampered.name))
    rep = install(str(tampered))
    story.append({**rep, "current_after": ota.current_version()})
    res = {"sequence": ["install v1", "install v2 (upgrade)", "install v3-broken (must roll back)",
                        "install tampered v2 (must be rejected)"],
           "final_current": ota.current_version(),
           "passed": [s["current_after"] for s in story] == ["v1", "v2", "v2", "v2"],
           "installs": story}
    write_json("M4", "ota", res)
    print("current after each step:", [s["current_after"] for s in story], "PASS" if res["passed"] else "FAIL")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "install", "status", "rollback", "demo"])
    ap.add_argument("bundle", nargs="?")
    args = ap.parse_args()
    setup_logging(load_config(), "ota")
    if args.cmd == "build":
        build()
    elif args.cmd == "install":
        install(args.bundle)
    elif args.cmd == "status":
        print({"CURRENT": ota.current_version(), "releases": sorted(p.name for p in ota.RELEASES.glob("*") if p.is_dir())})
    elif args.cmd == "rollback":
        print("rolled back to", ota.rollback())
    else:
        demo()


if __name__ == "__main__":
    main()
