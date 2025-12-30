from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

from dmc_ai_mobility.core.timing import wall_clock_ms

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LidarPoint:
    angle_rad: float
    range_m: float
    intensity: Optional[float] = None


@dataclass(frozen=True)
class LidarScan:
    points: list[LidarPoint]
    ts_ms: int


class LidarDriver(Protocol):
    def read(self) -> Optional[LidarScan]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class YdLidarConfig:
    serial_port: str = "/dev/ttyAMA0"
    serial_baudrate: int = 230400
    lidar_type: int = 0
    device_type: int = 0
    scan_frequency_hz: float = 7.0
    sample_rate: int = 4
    single_channel: bool = True
    intensity: bool = True
    min_angle_deg: float = -180.0
    max_angle_deg: float = 180.0
    min_range_m: float = 0.1
    max_range_m: float = 16.0


class MockLidarDriver:
    def __init__(self) -> None:
        self._closed = False
        self._seq = 0

    def read(self) -> Optional[LidarScan]:
        if self._closed:
            return None
        # Deterministic synthetic scan: enough structure for examples/tests.
        self._seq += 1
        base = 1.0 + 0.05 * ((self._seq % 20) - 10) / 10.0
        points: list[LidarPoint] = []
        for deg in range(-180, 181, 10):
            rng = base
            if abs(deg) <= 10:
                rng = 0.6
            points.append(LidarPoint(angle_rad=(deg * 3.141592653589793 / 180.0), range_m=rng))
        return LidarScan(points=points, ts_ms=wall_clock_ms())

    def close(self) -> None:
        self._closed = True


class YdLidarDriver:
    def __init__(self, config: YdLidarConfig) -> None:
        try:
            from dmc_ai_mobility.drivers import ydlidar  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "YDLidar SDK is not available. "
                "Verify `src/dmc_ai_mobility/drivers/_ydlidar.so` is built for this platform, "
                "or run the example with `--mock`."
            ) from e

        self._ydlidar = ydlidar
        self._closed = False
        self._fail_count = 0
        self._last_warn_ms = 0.0

        self._ydlidar.os_init()

        self._laser = self._ydlidar.CYdLidar()
        self._scan = self._ydlidar.LaserScan()

        cfg = config
        lt = cfg.lidar_type if cfg.lidar_type else self._ydlidar.TYPE_TRIANGLE
        dt = cfg.device_type if cfg.device_type else self._ydlidar.YDLIDAR_TYPE_SERIAL
        self._laser.setlidaropt(self._ydlidar.LidarPropSerialPort, cfg.serial_port)
        self._laser.setlidaropt(self._ydlidar.LidarPropSerialBaudrate, int(cfg.serial_baudrate))
        self._laser.setlidaropt(self._ydlidar.LidarPropLidarType, lt)
        self._laser.setlidaropt(self._ydlidar.LidarPropDeviceType, dt)
        self._laser.setlidaropt(self._ydlidar.LidarPropScanFrequency, float(cfg.scan_frequency_hz))
        self._laser.setlidaropt(self._ydlidar.LidarPropSampleRate, int(cfg.sample_rate))
        self._laser.setlidaropt(self._ydlidar.LidarPropSingleChannel, bool(cfg.single_channel))
        self._laser.setlidaropt(self._ydlidar.LidarPropIntenstiy, bool(cfg.intensity))
        self._laser.setlidaropt(self._ydlidar.LidarPropMaxAngle, float(cfg.max_angle_deg))
        self._laser.setlidaropt(self._ydlidar.LidarPropMinAngle, float(cfg.min_angle_deg))
        self._laser.setlidaropt(self._ydlidar.LidarPropMaxRange, float(cfg.max_range_m))
        self._laser.setlidaropt(self._ydlidar.LidarPropMinRange, float(cfg.min_range_m))

        if not self._laser.initialize():
            raise RuntimeError(f"LiDAR initialize failed (port={cfg.serial_port})")
        if not self._laser.turnOn():
            raise RuntimeError("LiDAR turnOn failed")

    def read(self) -> Optional[LidarScan]:
        if self._closed:
            return None

        ok = False
        try:
            ok = bool(self._laser.doProcessSimple(self._scan))
        except Exception:
            ok = False

        if not ok:
            self._fail_count += 1
            now_ms = time.monotonic() * 1000.0
            if now_ms - self._last_warn_ms > 5000:
                logger.warning("lidar read failed (fails=%d)", self._fail_count)
                self._last_warn_ms = now_ms
            return None

        self._fail_count = 0

        points_native: list[LidarPoint] = []
        try:
            pts = self._scan.points
            count = int(pts.size())
            for i in range(count):
                p = pts[i]
                rng = float(p.range)
                if rng == 0.0:
                    continue
                intensity = None
                if hasattr(p, "intensity"):
                    try:
                        intensity = float(p.intensity)
                    except Exception:
                        intensity = None
                points_native.append(LidarPoint(angle_rad=float(p.angle), range_m=rng, intensity=intensity))
        except Exception:
            return None

        return LidarScan(points=points_native, ts_ms=wall_clock_ms())

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            try:
                self._laser.turnOff()
            except Exception:
                pass
            try:
                self._laser.disconnecting()
            except Exception:
                pass
        finally:
            return
