"""M4.6: watch the PLC tags the station writes and log every change (works against OpenPLC, a real PLC, or plc_sim.py).

    python scripts/plc_watch.py --seconds 30                       # laptop: simulator on 127.0.0.1:5020
    EDGE_TARGET=pi python scripts/plc_watch.py --seconds 60         # Pi: OpenPLC on 127.0.0.1:502
-> evidence/M4/plc_link_<host>.json + .csv   (each change of coil %QX0.0 and register %QW0 with a timestamp)
"""

from __future__ import annotations

import argparse
import time

from edgevision.config import load_config
from edgevision.evidence import write_csv, write_json
from edgevision.hal import make_plc
from edgevision.hostinfo import host_tag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--hz", type=float, default=50)
    args = ap.parse_args()
    cfg = load_config()
    p = cfg["plc"]
    plc = make_plc({**p, "type": "modbus"})
    coil, reg = p.get("coil", 0), p.get("register", 0)
    t0 = time.perf_counter()
    last = (None, None)
    changes = []
    while time.perf_counter() - t0 < args.seconds:
        now = (plc.read_coil(coil), plc.read_register(reg))
        if now != last:
            row = {"t_s": round(time.perf_counter() - t0, 3), "coil_QX0_0": int(now[0]), "register_QW0": now[1]}
            changes.append(row)
            print(row, flush=True)
            last = now
        time.sleep(1 / args.hz)
    plc.close()
    rises = sum(1 for a, b in zip(changes, changes[1:]) if a["coil_QX0_0"] == 0 and b["coil_QX0_0"] == 1)
    write_csv("M4", f"plc_link_{host_tag()}", changes)
    write_json("M4", f"plc_link_{host_tag()}", {
        "server": f"{p['host']}:{p['port']} ({'OpenPLC / real PLC' if p['port'] == 502 else 'laptop Modbus simulator'})",
        "tags": {"coil": f"{coil} (%QX0.{coil}) pulses on each trigger",
                 "register": f"{reg} (%QW{reg}) = trigger count"},
        "watch_seconds": args.seconds, "coil_rising_edges": rises,
        "final_register": changes[-1]["register_QW0"] if changes else None, "changes": changes})
    print(f"coil pulses seen: {rises}, register now {changes[-1]['register_QW0'] if changes else None}")


if __name__ == "__main__":
    main()
