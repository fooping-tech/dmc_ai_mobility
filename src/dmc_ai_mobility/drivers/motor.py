from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class MotorDriver(Protocol):
    def set_velocity_mps(self, v_l: float, v_r: float) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


class MockMotorDriver:
    def __init__(self) -> None:
        self._last = (0.0, 0.0)

    def set_velocity_mps(self, v_l: float, v_r: float) -> None:
        self._last = (v_l, v_r)
        logger.info("mock motor set v_l=%.3f v_r=%.3f (mps)", v_l, v_r)

    def stop(self) -> None:
        if self._last != (0.0, 0.0):
            logger.info("mock motor stop")
        self._last = (0.0, 0.0)

    def close(self) -> None:
        self.stop()


@dataclass(frozen=True)
class PigpioMotorConfig:
    pin_l: int = 19
    pin_r: int = 12
    trim: float = 0.0
    neutral_pw: int = 1500
    gain_pw_per_unit: float = 500.0


class PigpioMotorDriver:
    def __init__(self, config: PigpioMotorConfig) -> None:
        try:
            import pigpio  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("pigpio is required for PigpioMotorDriver") from e

        self._pigpio = pigpio
        self._pi = pigpio.pi()
        if not self._pi.connected:  # pragma: no cover
            raise RuntimeError("pigpio daemon is not running or not reachable")
        self._cfg = config

    def set_velocity_mps(self, v_l: float, v_r: float) -> None:
        # Hardware mapping is project-specific; this provides a safe, simple placeholder:
        # - both motors centered at neutral pulse width
        # - apply trim and invert right channel as in calibration script conventions
        v_l_adj = v_l
        v_r_adj = v_r
        if self._cfg.trim:
            v_l_adj = v_l * (1.0 - self._cfg.trim)
            v_r_adj = v_r * (1.0 + self._cfg.trim)

        pw_l = int(self._cfg.neutral_pw + v_l_adj * self._cfg.gain_pw_per_unit)
        pw_r = int(self._cfg.neutral_pw - v_r_adj * self._cfg.gain_pw_per_unit)
        self._pi.set_servo_pulsewidth(self._cfg.pin_l, pw_l)
        self._pi.set_servo_pulsewidth(self._cfg.pin_r, pw_r)

    def stop(self) -> None:
        self._pi.set_servo_pulsewidth(self._cfg.pin_l, 0)
        self._pi.set_servo_pulsewidth(self._cfg.pin_r, 0)

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._pi.stop()
