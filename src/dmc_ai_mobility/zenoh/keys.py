from __future__ import annotations


def _robot_prefix(robot_id: str) -> str:
    if not robot_id or "/" in robot_id:
        raise ValueError("robot_id must be non-empty and must not contain '/'")
    return f"dmc_robo/{robot_id}"


def motor_cmd(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/motor/cmd"


def motor_telemetry(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/motor/telemetry"


def imu_state(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/imu/state"


def oled_cmd(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/oled/cmd"


def oled_image_mono1(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/oled/image/mono1"


def oled_mode(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/oled/mode"


def camera_image_jpeg(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/camera/image/jpeg"


def camera_meta(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/camera/meta"


def camera_video_h264(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/camera/video/h264"


def camera_video_h264_meta(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/camera/video/h264/meta"


def health_state(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/health/state"


def lidar_scan(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/lidar/scan"


def lidar_front(robot_id: str) -> str:
    return f"{_robot_prefix(robot_id)}/lidar/front"
