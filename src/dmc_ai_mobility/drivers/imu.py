from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from dmc_ai_mobility.core.timing import wall_clock_ms
from dmc_ai_mobility.core.types import ImuState

logger = logging.getLogger(__name__)


def _load_imu_offsets(path: Path) -> tuple[float, float, float, float, float, float]:
    try:
        if not path.exists():
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            float(data.get("gx_off") or 0.0),
            float(data.get("gy_off") or 0.0),
            float(data.get("gz_off") or 0.0),
            float(data.get("ax_off") or 0.0),
            float(data.get("ay_off") or 0.0),
            float(data.get("az_off") or 0.0),
        )
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


class ImuDriver(Protocol):
    def read(self) -> ImuState: ...
    def close(self) -> None: ...


class MockImuDriver:
    def read(self) -> ImuState:
        return ImuState(gx=0.0, gy=0.0, gz=0.0, ax=0.0, ay=0.0, az=0.0, ts_ms=wall_clock_ms())

    def close(self) -> None:
        return


@dataclass(frozen=True)
class MpuImuConfig:
    bus: int = 1
    address: int = 0x68


class Mpu9250ImuDriver:
    def __init__(self, config: MpuImuConfig) -> None:
        try:
            from mpu9250_jmdev.mpu_9250 import MPU9250  # type: ignore
            from mpu9250_jmdev.registers import (  # type: ignore
                AFS_8G,
                AK8963_BIT_16,
                AK8963_MODE_C100HZ,
                GFS_1000,
            )
        except Exception as e:  # pragma: no cover
            raise RuntimeError("mpu9250_jmdev is required for Mpu9250ImuDriver") from e

        self._mpu = MPU9250(
            bus=config.bus,
            address_mpu_master=config.address,
            gfs=GFS_1000,
            afs=AFS_8G,
            mfs=AK8963_BIT_16,
            mode=AK8963_MODE_C100HZ,
        )
        try:
            self._mpu.configure()
        except OSError:  # pragma: no cover
            logger.warning("IMU magnetometer init failed; continuing with gyro only")

        self._gx_off, self._gy_off, self._gz_off, self._ax_off, self._ay_off, self._az_off = _load_imu_offsets(
            Path("configs/imu_config.json")
        )
        self._accel_reader: Optional[Callable[[], tuple[float, float, float]]] = None
        if hasattr(self._mpu, "readAccelerometerMaster"):
            self._accel_reader = self._mpu.readAccelerometerMaster
        elif hasattr(self._mpu, "readAccelerometer"):
            self._accel_reader = self._mpu.readAccelerometer
        else:
            logger.warning("IMU accelerometer read is not available in this driver")

    def read(self) -> ImuState:
        gx, gy, gz = self._mpu.readGyroscopeMaster()
        ax = ay = az = 0.0
        if self._accel_reader is not None:
            ax, ay, az = self._accel_reader()
        return ImuState(
            gx=float(gx) - self._gx_off,
            gy=float(gy) - self._gy_off,
            gz=float(gz) - self._gz_off,
            ax=float(ax) - self._ax_off,
            ay=float(ay) - self._ay_off,
            az=float(az) - self._az_off,
            ts_ms=wall_clock_ms(),
        )

    def close(self) -> None:
        return
