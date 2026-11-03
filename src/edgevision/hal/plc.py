"""PLC HAL: Modbus TCP client (OpenPLC or a real PLC) and an in-memory fake."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Plc(ABC):
    @abstractmethod
    def write_coil(self, address: int, value: bool) -> None: ...

    @abstractmethod
    def read_coil(self, address: int) -> bool: ...

    @abstractmethod
    def write_register(self, address: int, value: int) -> None: ...

    @abstractmethod
    def read_register(self, address: int) -> int: ...

    def close(self) -> None:
        pass


class FakePlc(Plc):
    def __init__(self) -> None:
        self.coils: dict[int, bool] = {}
        self.registers: dict[int, int] = {}

    def write_coil(self, address: int, value: bool) -> None:
        self.coils[address] = value

    def read_coil(self, address: int) -> bool:
        return self.coils.get(address, False)

    def write_register(self, address: int, value: int) -> None:
        self.registers[address] = value & 0xFFFF

    def read_register(self, address: int) -> int:
        return self.registers.get(address, 0)


class ModbusPlc(Plc):
    """OpenPLC maps coil 0 -> %QX0.0 and holding register 0 -> %QW0 (or %MW0 from 1024)."""

    def __init__(self, host: str, port: int = 502, unit_id: int = 1) -> None:
        from pymodbus.client import ModbusTcpClient

        self._c = ModbusTcpClient(host, port=port, timeout=2)
        if not self._c.connect():
            raise ConnectionError(f"cannot reach Modbus server {host}:{port}")
        self._unit = unit_id

    def _ok(self, rr: Any) -> Any:
        if rr.isError():
            raise IOError(str(rr))
        return rr

    # pymodbus 3.7+ renamed slave= to device_id=; try both so either version works.
    def _call(self, fn: Any, *args: Any) -> Any:
        try:
            return self._ok(fn(*args, device_id=self._unit))
        except TypeError:
            return self._ok(fn(*args, slave=self._unit))

    def write_coil(self, address: int, value: bool) -> None:
        self._call(self._c.write_coil, address, value)

    def read_coil(self, address: int) -> bool:
        return bool(self._call(self._c.read_coils, address).bits[0])

    def write_register(self, address: int, value: int) -> None:
        self._call(self._c.write_register, address, value & 0xFFFF)

    def read_register(self, address: int) -> int:
        return int(self._call(self._c.read_holding_registers, address).registers[0])

    def close(self) -> None:
        self._c.close()


def make_plc(cfg: dict[str, Any]) -> Plc:
    kind = cfg.get("type", "fake")
    if kind == "fake":
        return FakePlc()
    if kind == "modbus":
        return ModbusPlc(cfg.get("host", "127.0.0.1"), cfg.get("port", 502), cfg.get("unit_id", 1))
    raise ValueError(f"unknown plc type {kind}")
