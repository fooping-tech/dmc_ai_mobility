from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

_PIGPIO_SERVO_MIN_PW = 500
_PIGPIO_SERVO_MAX_PW = 2500


def _clamp_int(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


@dataclass(frozen=True)
class MotorPulsewidth:
    pw_l: int
    pw_r: int
    pw_l_raw: int
    pw_r_raw: int
    pw_l_clamped: int
    pw_r_clamped: int


def _compute_pulsewidths(v_l: float, v_r: float, cfg: "PigpioMotorConfig") -> MotorPulsewidth:
    # Hardware mapping is project-specific; this provides a safe, simple placeholder:
    # - both motors centered at neutral pulse width
    # - apply trim and invert right channel as in calibration script conventions
    v_l_adj = v_l
    v_r_adj = v_r
    if cfg.trim:
        v_l_adj = v_l * (1.0 - cfg.trim)
        v_r_adj = v_r * (1.0 + cfg.trim)

    pw_l_raw = int(cfg.neutral_pw + v_l_adj * cfg.gain_pw_per_unit)
    pw_r_raw = int(cfg.neutral_pw - v_r_adj * cfg.gain_pw_per_unit)
    pw_l_clamped = _clamp_int(pw_l_raw, _PIGPIO_SERVO_MIN_PW, _PIGPIO_SERVO_MAX_PW)
    pw_r_clamped = _clamp_int(pw_r_raw, _PIGPIO_SERVO_MIN_PW, _PIGPIO_SERVO_MAX_PW)

    pw_l = pw_l_clamped
    pw_r = pw_r_clamped
    deadband_pw = int(cfg.deadband_pw)
    if deadband_pw > 0:
        n = int(cfg.neutral_pw)
        if abs(pw_l - n) <= deadband_pw and abs(pw_r - n) <= deadband_pw:
            pw_l = 0
            pw_r = 0

    return MotorPulsewidth(
        pw_l=pw_l,
        pw_r=pw_r,
        pw_l_raw=pw_l_raw,
        pw_r_raw=pw_r_raw,
        pw_l_clamped=pw_l_clamped,
        pw_r_clamped=pw_r_clamped,
    )


class MotorDriver(Protocol):
    def set_velocity_mps(self, v_l: float, v_r: float) -> None: ...
    def get_last_pulsewidths(self) -> MotorPulsewidth: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


class MockMotorDriver:
    def __init__(self, config: Optional["PigpioMotorConfig"] = None) -> None:
        self._cfg = config or PigpioMotorConfig()
        self._last = (0.0, 0.0)
        self._last_pulsewidth = MotorPulsewidth(0, 0, 0, 0, 0, 0)

    def set_velocity_mps(self, v_l: float, v_r: float) -> None:
        self._last = (v_l, v_r)
        self._last_pulsewidth = _compute_pulsewidths(v_l, v_r, self._cfg)
        logger.info("mock motor set v_l=%.3f v_r=%.3f (mps)", v_l, v_r)

    def get_last_pulsewidths(self) -> MotorPulsewidth:
        return self._last_pulsewidth

    def stop(self) -> None:
        if self._last != (0.0, 0.0):
            logger.info("mock motor stop")
        self._last = (0.0, 0.0)
        self._last_pulsewidth = MotorPulsewidth(0, 0, 0, 0, 0, 0)

    def close(self) -> None:
        self.stop()


@dataclass(frozen=True)
class PigpioMotorConfig:
    pin_l: int = 19
    pin_r: int = 12
    trim: float = 0.0
    neutral_pw: int = 1500
    gain_pw_per_unit: float = 500.0
    deadband_pw: int = 0
    print_pulsewidth: bool = False


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
        self._last_clamp_warn_ms = 0.0
        self._last_pulsewidth = MotorPulsewidth(0, 0, 0, 0, 0, 0)

    def set_velocity_mps(self, v_l: float, v_r: float) -> None:
        pw = _compute_pulsewidths(v_l, v_r, self._cfg)
        if (pw.pw_l_clamped != pw.pw_l_raw) or (pw.pw_r_clamped != pw.pw_r_raw):
            now_ms = time.monotonic() * 1000.0
            if now_ms - self._last_clamp_warn_ms > 5000.0:
                logger.warning(
                    "motor pulsewidth clamped (pw_l=%d->%d pw_r=%d->%d). "
                    "Check motor cmd magnitude and configs/motor_config.json trim.",
                    pw.pw_l_raw,
                    pw.pw_l_clamped,
                    pw.pw_r_raw,
                    pw.pw_r_clamped,
                )
                self._last_clamp_warn_ms = now_ms
        self._pi.set_servo_pulsewidth(self._cfg.pin_l, pw.pw_l)
        self._pi.set_servo_pulsewidth(self._cfg.pin_r, pw.pw_r)
        self._last_pulsewidth = pw
        if self._cfg.print_pulsewidth:
            print(
                f"motor pw: pin_l={self._cfg.pin_l} pw_l={pw.pw_l} (raw={pw.pw_l_raw}) | "
                f"pin_r={self._cfg.pin_r} pw_r={pw.pw_r} (raw={pw.pw_r_raw})",
                flush=True,
            )

    def get_last_pulsewidths(self) -> MotorPulsewidth:
        return self._last_pulsewidth

    def stop(self) -> None:
        self._pi.set_servo_pulsewidth(self._cfg.pin_l, 0)
        self._pi.set_servo_pulsewidth(self._cfg.pin_r, 0)
        self._last_pulsewidth = MotorPulsewidth(0, 0, 0, 0, 0, 0)
        if self._cfg.print_pulsewidth:
            print(
                f"motor pw: pin_l={self._cfg.pin_l} pw_l=0 | pin_r={self._cfg.pin_r} pw_r=0",
                flush=True,
            )

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._pi.stop()
