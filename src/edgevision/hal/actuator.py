"""Actuator HAL: one digital output (relay / LED). set(True) = output energised.

The station uses two of them:
  run_permit - energised only while the system is healthy; de-energised = conveyor STOP (fail-safe:
               a crash or power loss also de-energises it, so the safe state needs no working software)
  reject     - pulsed when the decision rule fires (reject gate / alarm LED)
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any


class Actuator(ABC):
    def __init__(self, name: str = "actuator", quiet: bool = False) -> None:
        self.name = name
        self.quiet = quiet
        self.state = False
        self.history: list[tuple[float, str]] = []   # (perf_counter, event)
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    @abstractmethod
    def _write(self, on: bool) -> None: ...

    def set(self, on: bool, reason: str = "") -> float:
        """Drive the output; returns perf_counter() right after the command was issued."""
        with self._lock:
            self._write(on)
            t = time.perf_counter()
            self.state = on
            self.history.append((t, f"{'ON' if on else 'OFF'} {reason}".strip()))
            return t

    def pulse(self, seconds: float, reason: str = "") -> float:
        if self._timer:
            self._timer.cancel()
        t = self.set(True, reason)
        self._timer = threading.Timer(seconds, self.set, args=(False, "pulse end"))
        self._timer.daemon = True
        self._timer.start()
        return t

    def close(self) -> None:
        if self._timer:
            self._timer.cancel()


class ConsoleActuator(Actuator):
    def _write(self, on: bool) -> None:
        if not self.quiet:
            print(f"[{self.name.upper()}] {'ON  (energised)' if on else 'OFF (de-energised)'}", flush=True)


class GpioActuator(Actuator):
    def __init__(self, pin: int, active_high: bool = True, name: str = "actuator") -> None:
        super().__init__(name)
        from gpiozero import DigitalOutputDevice  # only on the Pi

        self._dev = DigitalOutputDevice(pin, active_high=active_high, initial_value=False)

    def _write(self, on: bool) -> None:
        self._dev.value = 1 if on else 0

    def close(self) -> None:
        super().close()
        self._dev.off()      # leave the pin de-energised = safe
        self._dev.close()


def make_actuator(cfg: dict[str, Any], name: str = "actuator", quiet: bool = False) -> Actuator:
    kind = cfg.get("type", "console")
    if kind == "console":
        return ConsoleActuator(name, quiet)
    if kind == "gpio":
        return GpioActuator(cfg.get("pin", 17), cfg.get("active_high", True), name)
    raise ValueError(f"unknown actuator type {kind}")
