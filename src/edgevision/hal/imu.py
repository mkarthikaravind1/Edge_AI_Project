"""IMU HAL: MPU6050 on the Pi, CSV replay on the laptop. Units: accel in g, gyro in deg/s."""

from __future__ import annotations

import csv
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator

COLUMNS = ["t", "ax", "ay", "az", "gx", "gy", "gz"]


@dataclass
class ImuSample:
    t: float
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float

    def as_row(self) -> list[float]:
        return [self.t, self.ax, self.ay, self.az, self.gx, self.gy, self.gz]


class Imu(ABC):
    @abstractmethod
    def read(self) -> ImuSample | None: ...

    def stream(self, rate_hz: float, duration_s: float | None = None) -> Iterator[ImuSample]:
        period = 1.0 / rate_hz
        t0 = time.perf_counter()
        nxt = t0
        while duration_s is None or time.perf_counter() - t0 < duration_s:
            s = self.read()
            if s is None:
                return
            yield s
            nxt += period
            delay = nxt - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

    def close(self) -> None:
        pass


class CsvReplayImu(Imu):
    def __init__(self, path: str, loop: bool = False) -> None:
        with open(path, newline="", encoding="utf-8") as f:
            self._rows = [ImuSample(*(float(r[c]) for c in COLUMNS)) for r in csv.DictReader(f)]
        self._i = 0
        self._loop = loop

    def read(self) -> ImuSample | None:
        if self._i >= len(self._rows):
            if not self._loop:
                return None
            self._i = 0
        s = self._rows[self._i]
        self._i += 1
        return s


class Mpu6050Imu(Imu):
    """Raw register access via smbus2. ±2 g and ±250 deg/s ranges (power-on defaults)."""

    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B

    def __init__(self, bus: int = 1, address: int = 0x68) -> None:
        from smbus2 import SMBus  # only on the Pi

        self._bus = SMBus(bus)
        self._addr = address
        self._bus.write_byte_data(address, self.PWR_MGMT_1, 0)   # wake up
        self._t0 = time.perf_counter()

    @staticmethod
    def _s16(hi: int, lo: int) -> int:
        v = (hi << 8) | lo
        return v - 65536 if v > 32767 else v

    def read(self) -> ImuSample | None:
        try:
            d = self._bus.read_i2c_block_data(self._addr, self.ACCEL_XOUT_H, 14)
        except OSError:
            return None
        ax, ay, az = (self._s16(d[i], d[i + 1]) / 16384.0 for i in (0, 2, 4))
        gx, gy, gz = (self._s16(d[i], d[i + 1]) / 131.0 for i in (8, 10, 12))
        return ImuSample(time.perf_counter() - self._t0, ax, ay, az, gx, gy, gz)

    def close(self) -> None:
        self._bus.close()


def make_imu(cfg: dict[str, Any]) -> Imu:
    from ..config import resolve

    kind = cfg.get("type", "csv_replay")
    if kind == "csv_replay":
        return CsvReplayImu(str(resolve(cfg["path"])), cfg.get("loop", False))
    if kind == "mpu6050":
        return Mpu6050Imu(cfg.get("i2c_bus", 1), cfg.get("address", 0x68))
    raise ValueError(f"unknown imu type {kind}")
