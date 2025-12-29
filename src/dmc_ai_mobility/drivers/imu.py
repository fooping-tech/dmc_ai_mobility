from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from dmc_ai_mobility.core.timing import wall_clock_ms
from dmc_ai_mobility.core.types import ImuState

logger = logging.getLogger(__name__)


class ImuDriver(Protocol):
    def read(self) -> ImuState: ...
    def close(self) -> None: ...


class MockImuDriver:
    def read(self) -> ImuState:
        return ImuState(gx=0.0, gy=0.0, gz=0.0, ts_ms=wall_clock_ms())

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

    def read(self) -> ImuState:
        gx, gy, gz = self._mpu.readGyroscopeMaster()
        return ImuState(gx=float(gx), gy=float(gy), gz=float(gz), ts_ms=wall_clock_ms())

    def close(self) -> None:
        return
