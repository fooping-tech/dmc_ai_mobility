from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field} must be a number")


def _optional_int(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an int")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    raise ValueError(f"{field} must be an int")


@dataclass(frozen=True)
class MotorCmd:
    v_l: float
    v_r: float
    unit: str = "mps"
    deadman_ms: int = 300
    seq: Optional[int] = None
    ts_ms: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MotorCmd":
        v_l = _require_number(data.get("v_l"), "v_l")
        v_r = _require_number(data.get("v_r"), "v_r")
        unit = str(data.get("unit") or "mps")
        deadman_ms = int(data.get("deadman_ms") or 300)
        seq = _optional_int(data.get("seq"), "seq")
        ts_ms = _optional_int(data.get("ts_ms"), "ts_ms")
        return cls(v_l=v_l, v_r=v_r, unit=unit, deadman_ms=deadman_ms, seq=seq, ts_ms=ts_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v_l": self.v_l,
            "v_r": self.v_r,
            "unit": self.unit,
            "deadman_ms": self.deadman_ms,
            "seq": self.seq,
            "ts_ms": self.ts_ms,
        }


@dataclass(frozen=True)
class ImuState:
    gx: float
    gy: float
    gz: float
    ax: float
    ay: float
    az: float
    ts_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "ts_ms": self.ts_ms,
        }


@dataclass(frozen=True)
class OledCmd:
    text: str
    ts_ms: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OledCmd":
        text = str(data.get("text") or "")
        ts_ms = _optional_int(data.get("ts_ms"), "ts_ms")
        return cls(text=text, ts_ms=ts_ms)


@dataclass(frozen=True)
class OledModeCmd:
    mode: str
    settings_index: Optional[int] = None
    ts_ms: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OledModeCmd":
        mode = str(data.get("mode") or "")
        settings_index = _optional_int(data.get("settings_index"), "settings_index")
        ts_ms = _optional_int(data.get("ts_ms"), "ts_ms")
        return cls(mode=mode, settings_index=settings_index, ts_ms=ts_ms)


@dataclass(frozen=True)
class CameraMeta:
    width: int
    height: int
    fps: float
    seq: int
    ts_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "seq": self.seq,
            "ts_ms": self.ts_ms,
        }
