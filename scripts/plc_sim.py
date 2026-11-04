"""Laptop stand-in for OpenPLC: a Modbus TCP server with 100 coils and 100 holding registers.

OpenPLC maps Modbus coil 0 -> %QX0.0 and holding register 0 -> %QW0, so the station code is identical for both.
On the Pi this script is NOT used: OpenPLC (or the real PLC) is the server.

    python scripts/plc_sim.py --port 5020
"""

from __future__ import annotations

import argparse
import logging

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import StartTcpServer

try:                                     # pymodbus >= 3.9
    from pymodbus.datastore import ModbusDeviceContext as DeviceContext
except ImportError:                      # older pymodbus
    from pymodbus.datastore import ModbusSlaveContext as DeviceContext


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5020)
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)          # hide pymodbus v4 deprecation notices
    dev = DeviceContext(co=ModbusSequentialDataBlock(1, [False] * 101), hr=ModbusSequentialDataBlock(1, [0] * 101),
                        di=ModbusSequentialDataBlock(1, [False] * 101), ir=ModbusSequentialDataBlock(1, [0] * 101))
    try:
        ctx = ModbusServerContext(devices=dev, single=True)
    except TypeError:
        ctx = ModbusServerContext(slaves=dev, single=True)
    print(f"PLC simulator (Modbus TCP) on {args.host}:{args.port} - coils 0-99, holding registers 0-99", flush=True)
    StartTcpServer(context=ctx, address=(args.host, args.port))


if __name__ == "__main__":
    main()
