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


class OnboardLedActuator(Actuator):
    """One of the Raspberry Pi's own board LEDs as a visible output, when no external LED/relay is wired.

    led = "ACT" (green) or "PWR" (red), driven through /sys/class/leds/<led>/ (the kernel's activity trigger is
    switched off while we use it and restored on close). If `pin` is given the GPIO pin is driven as well, so an
    external LED/relay on that pin works with no config change, and `pinctrl get <pin>` shows the level.

    Writing to /sys/class/leds needs root, or the udev rule that deploy/pi_setup.sh installs (group gpio).
    Limit: a board LED is NOT fail-safe like a relay coil (it keeps its last state if the program is killed), so
    for run_permit it only *shows* the state; the GPIO pin is the real fail-safe output.
    """

    def __init__(self, led: str = "ACT", pin: int | None = None, active_high: bool = True, name: str = "actuator",
                 root: str = "/sys/class/leds") -> None:
        super().__init__(name)
        from pathlib import Path

        self._dir = Path(root) / led
        if not self._dir.exists():
            raise RuntimeError(f"board LED {led} not found in {root} (Pi only)")
        trig = (self._dir / "trigger").read_text().strip()
        cur = [w.strip("[]") for w in trig.split() if w.startswith("[")]
        self._old_trigger = cur[0] if cur else "none"
        try:
            (self._dir / "trigger").write_text("none")
        except PermissionError as e:
            raise RuntimeError(f"no permission for {self._dir}: run deploy/pi_setup.sh (udev rule) and reboot") from e
        self._gpio = GpioActuator(pin, active_high, name) if pin is not None else None
        self._write(False)

    def _write(self, on: bool) -> None:
        (self._dir / "brightness").write_text("1" if on else "0")
        if self._gpio is not None:
            self._gpio._write(on)

    def close(self) -> None:
        super().close()
        try:
            self._write(False)
            (self._dir / "trigger").write_text(self._old_trigger)   # give the LED back to the system
        except OSError:
            pass
        if self._gpio is not None:
            self._gpio.close()


def make_actuator(cfg: dict[str, Any], name: str = "actuator", quiet: bool = False) -> Actuator:
    kind = cfg.get("type", "console")
    if kind == "console":
        return ConsoleActuator(name, quiet)
    if kind == "gpio":
        return GpioActuator(cfg.get("pin", 17), cfg.get("active_high", True), name)
    if kind == "onboard_led":
        try:
            return OnboardLedActuator(cfg.get("led", "ACT"), cfg.get("pin"), cfg.get("active_high", True), name,
                                      cfg.get("leds_root", "/sys/class/leds"))
        except Exception as e:          # board LED missing / not writable: never stop the station for a light
            import logging
            logging.getLogger(__name__).warning("%s: board LED unavailable (%s); using %s", name, e,
                                                "GPIO only" if cfg.get("pin") is not None else "console")
            if cfg.get("pin") is not None:
                return GpioActuator(cfg["pin"], cfg.get("active_high", True), name)
            return ConsoleActuator(name, quiet)
    raise ValueError(f"unknown actuator type {kind}")
