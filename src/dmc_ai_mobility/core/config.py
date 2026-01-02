from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass(frozen=True)
class GpioConfig:
    pin_l: int = 19
    pin_r: int = 12
    sw1: int = 8
    sw2: int = 7


@dataclass(frozen=True)
class MotorConfig:
    deadman_ms: int = 300
    deadband_pw: int = 0
    telemetry_hz: float = 10.0


@dataclass(frozen=True)
class ImuConfig:
    publish_hz: float = 50.0


@dataclass(frozen=True)
class OledConfig:
    max_hz: float = 10.0
    i2c_port: int = 1
    i2c_address: int = 0x3C
    width: int = 128
    height: int = 32
    override_s: float = 2.0
    boot_image: Optional[str] = None
    motor_image: Optional[str] = None


@dataclass(frozen=True)
class CameraConfig:
    enable: bool = True
    device: int = 0
    width: int = 640
    height: int = 480
    fps: float = 10.0
    auto_trim: bool = False
    buffer_size: int = 0
    latest_only: bool = False


@dataclass(frozen=True)
class LidarConfig:
    enable: bool = False
    port: str = "/dev/ttyAMA0"
    baudrate: int = 230400
    publish_hz: float = 10.0
    front_window_deg: float = 10.0
    front_stat: str = "mean"  # "mean" or "min"


@dataclass(frozen=True)
class ZenohConfig:
    config_path: Optional[str] = None


@dataclass(frozen=True)
class RobotConfig:
    robot_id: str = "rasp-zero-01"
    gpio: GpioConfig = GpioConfig()
    motor: MotorConfig = MotorConfig()
    imu: ImuConfig = ImuConfig()
    oled: OledConfig = OledConfig()
    camera: CameraConfig = CameraConfig()
    lidar: LidarConfig = LidarConfig()
    zenoh: ZenohConfig = ZenohConfig()


def _get_section(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    section = data.get(key) or {}
    if isinstance(section, dict):
        return section
    return {}


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def load_config(path: Path, overrides: Optional[Dict[str, Any]] = None) -> RobotConfig:
    raw: Dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as f:
            raw = tomllib.load(f)

    if overrides:
        raw = _merge_dicts(raw, overrides)

    gpio = _get_section(raw, "gpio")
    motor = _get_section(raw, "motor")
    imu = _get_section(raw, "imu")
    oled = _get_section(raw, "oled")
    camera = _get_section(raw, "camera")
    lidar = _get_section(raw, "lidar")
    zenoh = _get_section(raw, "zenoh")

    return RobotConfig(
        robot_id=str(raw.get("robot_id") or "rasp-zero-01"),
        gpio=GpioConfig(
            pin_l=int(gpio.get("pin_l", GpioConfig.pin_l)),
            pin_r=int(gpio.get("pin_r", GpioConfig.pin_r)),
            sw1=int(gpio.get("sw1", GpioConfig.sw1)),
            sw2=int(gpio.get("sw2", GpioConfig.sw2)),
        ),
        motor=MotorConfig(
            deadman_ms=int(motor.get("deadman_ms", MotorConfig.deadman_ms)),
            deadband_pw=int(motor.get("deadband_pw", MotorConfig.deadband_pw)),
            telemetry_hz=float(motor.get("telemetry_hz", MotorConfig.telemetry_hz)),
        ),
        imu=ImuConfig(publish_hz=float(imu.get("publish_hz", ImuConfig.publish_hz))),
        oled=OledConfig(
            max_hz=float(oled.get("max_hz", OledConfig.max_hz)),
            i2c_port=int(oled.get("i2c_port", OledConfig.i2c_port)),
            i2c_address=int(oled.get("i2c_address", OledConfig.i2c_address)),
            width=int(oled.get("width", OledConfig.width)),
            height=int(oled.get("height", OledConfig.height)),
            override_s=float(oled.get("override_s", OledConfig.override_s)),
            boot_image=_optional_str(oled.get("boot_image")),
            motor_image=_optional_str(oled.get("motor_image")),
        ),
        camera=CameraConfig(
            enable=bool(camera.get("enable", CameraConfig.enable)),
            device=int(camera.get("device", CameraConfig.device)),
            width=int(camera.get("width", CameraConfig.width)),
            height=int(camera.get("height", CameraConfig.height)),
            fps=float(camera.get("fps", CameraConfig.fps)),
            auto_trim=bool(camera.get("auto_trim", CameraConfig.auto_trim)),
            buffer_size=int(camera.get("buffer_size", CameraConfig.buffer_size)),
            latest_only=bool(camera.get("latest_only", CameraConfig.latest_only)),
        ),
        lidar=LidarConfig(
            enable=bool(lidar.get("enable", LidarConfig.enable)),
            port=str(lidar.get("port", LidarConfig.port)),
            baudrate=int(lidar.get("baudrate", LidarConfig.baudrate)),
            publish_hz=float(lidar.get("publish_hz", LidarConfig.publish_hz)),
            front_window_deg=float(lidar.get("front_window_deg", LidarConfig.front_window_deg)),
            front_stat=str(lidar.get("front_stat", LidarConfig.front_stat)),
        ),
        zenoh=ZenohConfig(config_path=zenoh.get("config_path")),
    )


def _merge_dicts(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result
