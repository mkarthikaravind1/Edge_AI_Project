"""Actuator HAL: a relay / LED / conveyor-stop line. on() = action asserted."""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

log = logging.getLogger(__name__)


class Actuator(ABC):
    def __init__(self) -> None:
        self.state = False
        self.history: list[tuple[float, str]] = []   # (perf_counter, event)
        self._timer: threading.Timer | None = None

    @abstractmethod
    def _write(self, on: bool) -> None: ...

    def set(self, on: bool, reason: str = "") -> float:
        """Drive the output; returns perf_counter() right after the command was issued."""
        self._write(on)
        t = time.perf_counter()
        self.state = on
        self.history.append((t, f"{'ON' if on else 'OFF'} {reason}".strip()))
        return t

    def pulse(self, seconds: float, reason: str = "") -> float:
        t = self.set(True, reason)
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(seconds, self.set, args=(False, "pulse end"))
        self._timer.daemon = True
        self._timer.start()
        return t

    def close(self) -> None:
        if self._timer:
            self._timer.cancel()


class ConsoleActuator(Actuator):
    def _write(self, on: bool) -> None:
        print(f"[ACTUATOR] {'ON  >>> relay energised' if on else 'OFF'}", flush=True)


class GpioActuator(Actuator):
    def __init__(self, pin: int, active_high: bool = True) -> None:
        super().__init__()
        from gpiozero import DigitalOutputDevice  # only on the Pi

        self._dev = DigitalOutputDevice(pin, active_high=active_high, initial_value=False)

    def _write(self, on: bool) -> None:
        self._dev.value = 1 if on else 0

    def close(self) -> None:
        super().close()
        self._dev.close()


def make_actuator(cfg: dict[str, Any]) -> Actuator:
    kind = cfg.get("type", "console")
    if kind == "console":
        return ConsoleActuator()
    if kind == "gpio":
        return GpioActuator(cfg.get("pin", 17), cfg.get("active_high", True))
    raise ValueError(f"unknown actuator type {kind}")
