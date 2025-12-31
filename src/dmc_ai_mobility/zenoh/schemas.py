from __future__ import annotations

import json
from typing import Any, Dict


def encode_json(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def decode_json(payload: bytes) -> Dict[str, Any]:
    if not payload:
        return {}
    text = payload.decode("utf-8", errors="strict")
    value = json.loads(text)
    if isinstance(value, dict):
        return value
    raise ValueError("expected JSON object")


MOTOR_CMD_SCHEMA = {
    "key": "dmc_robo/<robot_id>/motor/cmd",
    "json": {
        "v_l": "number (left velocity)",
        "v_r": "number (right velocity)",
        "unit": "string (default: mps)",
        "deadman_ms": "int (default: 300)",
        "seq": "int (optional)",
        "ts_ms": "int (optional)",
    },
}

MOTOR_TELEMETRY_SCHEMA = {
    "key": "dmc_robo/<robot_id>/motor/telemetry",
    "json": {
        "pw_l": "int (pulsewidth left, after deadband)",
        "pw_r": "int (pulsewidth right, after deadband)",
        "pw_l_raw": "int (pulsewidth left, pre-clamp)",
        "pw_r_raw": "int (pulsewidth right, pre-clamp)",
        "cmd_v_l": "number|null (latest command left velocity)",
        "cmd_v_r": "number|null (latest command right velocity)",
        "cmd_unit": "string|null (default: mps)",
        "cmd_deadman_ms": "int|null",
        "cmd_seq": "int|null (optional)",
        "cmd_ts_ms": "int|null (optional)",
        "ts_ms": "int (publisher epoch ms)",
    },
}


OLED_CMD_SCHEMA = {
    "key": "dmc_robo/<robot_id>/oled/cmd",
    "json": {"text": "string", "ts_ms": "int (optional)"},
}


IMU_STATE_SCHEMA = {
    "key": "dmc_robo/<robot_id>/imu/state",
    "json": {
        "gx": "number",
        "gy": "number",
        "gz": "number",
        "ax": "number",
        "ay": "number",
        "az": "number",
        "ts_ms": "int",
    },
}


CAMERA_META_SCHEMA = {
    "key": "dmc_robo/<robot_id>/camera/meta",
    "json": {"width": "int", "height": "int", "fps": "number", "seq": "int", "ts_ms": "int"},
}
