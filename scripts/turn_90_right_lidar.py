#!/usr/bin/env python3
"""Turn robot by target degrees with IMU feedback and smooth slowdown (P control).

- Uses IMU gyro z (gx/gy/gz) as deg/s (or rad/s if specified) and integrates to
  estimate yaw change.
- Controls motor speed with proportional control so it slows down near target.
- Uses LiDAR scan for safety stop (optional but recommended).

This is intended for short in-place turns (e.g. 90 deg).

Safety/robustness:
- Gyro clamp + median filter to reduce spikes
- Direction gating: only integrates samples consistent with the commanded turn
- Timeout + stop + optional brake pulse

Example:
  python scripts/turn_90_right_lidar.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 --dir right
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _key(robot_id: str, suffix: str) -> str:
    if not robot_id or "/" in robot_id:
        raise SystemExit("robot_id must be non-empty and must not contain '/'")
    return f"dmc_robo/{robot_id}/{suffix}"


def _build_session_opener(config_path: Optional[Path], mode: str, connect_endpoints: list[str]):
    import zenoh

    if config_path is not None and not config_path.exists():
        raise SystemExit(f"zenoh config not found: {config_path}")

    if config_path:
        cfg = zenoh.Config.from_file(str(config_path))
    else:
        try:
            cfg = zenoh.Config.from_env()
        except Exception:
            cfg = zenoh.Config()

    if mode:
        cfg.insert_json5("mode", json.dumps(mode))
    if connect_endpoints:
        cfg.insert_json5("connect/endpoints", json.dumps(connect_endpoints))

    return lambda: zenoh.open(cfg)


@dataclass
class Latest:
    imu: Optional[dict[str, Any]] = None
    scan: Optional[dict[str, Any]] = None


def _get_by_path(obj: Any, path: str) -> Any:
    cur = obj
    if not path:
        return cur
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def extract_gyro_z(payload: Any) -> Optional[float]:
    """Try to extract gyro z from IMU payload."""
    if not isinstance(payload, dict):
        return None

    for base, key in (
        ("", "gz"),
        ("", "wz"),
        ("gyro", "z"),
        ("angular_velocity", "z"),
        ("ang_vel", "z"),
        ("w", "z"),
    ):
        obj = payload if not base else _get_by_path(payload, base)
        if isinstance(obj, dict):
            v = obj.get(key)
            if isinstance(v, (int, float)):
                return float(v)
    return None


def lidar_min_range(scan: Any, *, max_range_m: float = 8.0) -> float:
    if not isinstance(scan, dict):
        return float("inf")
    pts = scan.get("points")
    if not isinstance(pts, list) or not pts:
        return float("inf")
    m = float("inf")
    for p in pts:
        if not isinstance(p, dict):
            continue
        r = p.get("range_m")
        if isinstance(r, (int, float)):
            rr = float(r)
            if 0.0 < rr < max_range_m and rr < m:
                m = rr
    return m


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--dir", choices=["left", "right"], default="right")
    p.add_argument("--target-deg", type=float, default=90.0)

    # Control
    p.add_argument("--kp", type=float, default=0.0025, help="P gain: speed_cmd = kp * error_deg")
    p.add_argument("--min-speed", type=float, default=0.06, help="minimum |speed| while error > stop_band")
    p.add_argument("--max-speed", type=float, default=0.15, help="maximum |speed|")
    p.add_argument("--stop-band-deg", type=float, default=3.0, help="stop when error <= this")
    p.add_argument("--brake-ms", type=int, default=80, help="reverse pulse duration at stop (ms), 0 to disable")
    p.add_argument("--brake-speed", type=float, default=0.08, help="reverse pulse speed")

    # Motor message
    p.add_argument("--deadman-ms", type=int, default=300)
    p.add_argument("--hz", type=float, default=30.0)
    p.add_argument("--timeout-s", type=float, default=10.0)
    p.add_argument("--max-turn-s", type=float, default=2.0, help="hard stop even if target not reached")

    # Safety
    p.add_argument("--safety-stop-m", type=float, default=0.05)

    # IMU processing
    p.add_argument("--gyro-unit", choices=["degps", "radps"], default="degps")
    p.add_argument("--gz-max", type=float, default=720.0, help="clamp |gz| to this (in deg/s or rad/s) before filtering")
    p.add_argument("--start-gz", type=float, default=15.0, help="require |gz_dir| >= this to consider it 'turning'")
    p.add_argument("--median-n", type=int, default=5)

    args = p.parse_args(argv)

    target_deg = float(args.target_deg)
    loop_dt = 1.0 / max(1.0, float(args.hz))

    # dir_sign makes "progress" positive for both directions
    dir_sign = +1.0 if args.dir == "right" else -1.0

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()
    latest = Latest()

    def on_imu(sample: Any) -> None:
        try:
            latest.imu = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    def on_scan(sample: Any) -> None:
        try:
            latest.scan = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    key_imu = _key(str(args.robot_id), "imu/state")
    key_scan = _key(str(args.robot_id), "lidar/scan")
    key_motor = _key(str(args.robot_id), "motor/cmd")

    pub_motor = sess.declare_publisher(key_motor)
    sub_imu = sess.declare_subscriber(key_imu, on_imu)
    sub_scan = sess.declare_subscriber(key_scan, on_scan)

    def publish_motor(v_l: float, v_r: float) -> None:
        payload = {
            "v_l": float(v_l),
            "v_r": float(v_r),
            "unit": "mps",
            "deadman_ms": int(args.deadman_ms),
            "seq": int(time.time() * 1000) % 1_000_000_000,
            "ts_ms": int(time.time() * 1000),
        }
        pub_motor.put(json.dumps(payload).encode("utf-8"))

    def stop(repeat: int = 6) -> None:
        for _ in range(max(1, int(repeat))):
            publish_motor(0.0, 0.0)
            time.sleep(0.05)

    def command_turn(speed_abs: float) -> None:
        s = float(speed_abs)
        s = abs(s)
        if args.dir == "right":
            publish_motor(+s, -s)
        else:
            publish_motor(-s, +s)

    def command_brake() -> None:
        if int(args.brake_ms) <= 0:
            return
        bs = float(args.brake_speed)
        bs = abs(bs)
        # opposite direction
        if args.dir == "right":
            publish_motor(-bs, +bs)
        else:
            publish_motor(+bs, -bs)
        time.sleep(max(0.0, int(args.brake_ms) / 1000.0))

    try:
        # Wait for first IMU
        t0 = time.monotonic()
        while latest.imu is None and time.monotonic() - t0 < 2.0:
            time.sleep(0.02)
        if latest.imu is None:
            raise SystemExit("imu/state not received (timeout)")

        progress_deg = 0.0  # positive = turning in requested direction
        last_t = time.monotonic()
        start_t = last_t

        gz_hist: list[float] = []  # in deg/s after direction sign

        print(
            f"[turn] dir={args.dir} target={target_deg:.1f}deg kp={args.kp} min={args.min_speed} max={args.max_speed} "
            f"stop_band={args.stop_band_deg} brake_ms={args.brake_ms} gyro_unit={args.gyro_unit}"
        )

        while True:
            now = time.monotonic()
            if now - start_t > float(args.timeout_s):
                print("[turn] timeout -> stop")
                break

            mr = lidar_min_range(latest.scan)
            if mr != float("inf") and mr < float(args.safety_stop_m):
                print(f"[turn] safety stop: min_range={mr:.2f}m")
                break

            gz = extract_gyro_z(latest.imu)
            if gz is None:
                print("[turn] gyro z not found -> stop")
                break

            # convert to deg/s
            gz_val = float(gz)
            if args.gyro_unit == "radps":
                gz_deg_s = gz_val * (180.0 / math.pi)
                gz_max = float(args.gz_max) * (180.0 / math.pi)
            else:
                gz_deg_s = gz_val
                gz_max = float(args.gz_max)

            # direction sign: make desired direction positive
            gz_dir = dir_sign * gz_deg_s

            # clamp
            gz_dir = _clamp(gz_dir, -gz_max, +gz_max)

            # median filter
            gz_hist.append(gz_dir)
            n = max(1, int(args.median_n))
            if len(gz_hist) > n:
                gz_hist = gz_hist[-n:]
            gz_med = sorted(gz_hist)[len(gz_hist) // 2]

            # Only integrate when it indicates turning in the desired direction.
            # (If it goes negative, treat as 0 for progress.)
            if gz_med < 0.0:
                gz_med_for_int = 0.0
            else:
                gz_med_for_int = gz_med

            dt_i = max(0.0, min(0.2, now - last_t))
            last_t = now
            # Always integrate progress (prevents "turning but not counted" runaway)
            progress_deg += gz_med_for_int * dt_i

            turning_ok = gz_med_for_int >= float(args.start_gz)

            err = target_deg - progress_deg

            speed_cmd = float(args.kp) * err
            speed_cmd = _clamp(speed_cmd, 0.0, float(args.max_speed))

            # Before we're sure it's turning, keep a conservative minimum command.
            if not turning_ok:
                speed_cmd = float(args.min_speed)
            else:
                if err > float(args.stop_band_deg):
                    speed_cmd = max(speed_cmd, float(args.min_speed))

            print(
                f"[turn] prog={progress_deg:6.1f}deg err={err:6.1f}deg "
                f"gz_med={gz_med:7.1f}deg/s speed={speed_cmd:0.3f} min_range={mr:.2f}m"
            )

            if err <= float(args.stop_band_deg):
                print("[turn] reached target -> stop")
                break

            if progress_deg >= target_deg * 2.5:
                print("[turn] progress runaway guard -> stop")
                break

            if now - start_t >= float(args.max_turn_s):
                print("[turn] max_turn_s reached -> stop")
                break

            command_turn(speed_cmd)
            time.sleep(loop_dt)

        # Stop + optional brake
        command_brake()
        stop(repeat=6)

    finally:
        try:
            stop(repeat=3)
        except Exception:
            pass
        try:
            sub_imu.undeclare()
        except Exception:
            pass
        try:
            sub_scan.undeclare()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
