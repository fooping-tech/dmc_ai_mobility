from __future__ import annotations

import time


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def wall_clock_ms() -> int:
    return int(time.time() * 1000)


def sleep_s(seconds: float) -> None:
    if seconds <= 0:
        return
    time.sleep(seconds)


class PeriodicSleeper:
    def __init__(self, hz: float) -> None:
        if hz <= 0:
            raise ValueError("hz must be > 0")
        self._period_s = 1.0 / hz
        self._next_t = time.monotonic()

    def sleep(self) -> None:
        self._next_t += self._period_s
        delay = self._next_t - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            self._next_t = time.monotonic()
