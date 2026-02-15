from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OledSnapshot:
    mode: str  # locked | override | base
    kind: Optional[str] = None  # text | mono1
    text: str = ""
    mono1: bytes = b""


class OledArbiter:
    """Single-writer OLED arbitration helper.

    Priority:
      1) locked owner screen
      2) timed override (text/mono1)
      3) base renderer
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owner: Optional[str] = None
        self._locked_text: str = ""

        self._override_until_ms: int = 0
        self._override_kind: Optional[str] = None  # text | mono1
        self._override_text: str = ""
        self._override_mono1: bytes = b""

    def acquire(self, owner: str, text: str) -> None:
        with self._lock:
            self._owner = owner
            self._locked_text = text

    def release(self, owner: str) -> None:
        with self._lock:
            if self._owner == owner:
                self._owner = None
                self._locked_text = ""

    def is_locked(self) -> bool:
        with self._lock:
            return self._owner is not None

    def set_override_text(self, text: str, until_ms: int) -> bool:
        with self._lock:
            if self._owner is not None:
                return False
            self._override_kind = "text"
            self._override_text = text
            self._override_mono1 = b""
            self._override_until_ms = int(until_ms)
            return True

    def set_override_mono1(self, buf: bytes, until_ms: int) -> bool:
        with self._lock:
            if self._owner is not None:
                return False
            self._override_kind = "mono1"
            self._override_mono1 = bytes(buf)
            self._override_text = ""
            self._override_until_ms = int(until_ms)
            return True

    def snapshot(self, now_ms: int) -> OledSnapshot:
        with self._lock:
            if self._owner is not None:
                return OledSnapshot(mode="locked", kind="text", text=self._locked_text)

            if self._override_kind and now_ms < self._override_until_ms:
                return OledSnapshot(
                    mode="override",
                    kind=self._override_kind,
                    text=self._override_text,
                    mono1=self._override_mono1,
                )

            if self._override_kind and now_ms >= self._override_until_ms:
                self._override_kind = None
                self._override_text = ""
                self._override_mono1 = b""
                self._override_until_ms = 0

            return OledSnapshot(mode="base")
