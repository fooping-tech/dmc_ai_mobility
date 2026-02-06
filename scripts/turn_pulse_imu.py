#!/usr/bin/env python3
"""Pulse-based in-place turn using IMU feedback (robust against overshoot).

Instead of continuous control, this script:
- Sends short motor pulses to rotate.
- After each pulse, coasts briefly and integrates IMU gz to estimate angle change.
- Repeats until target is reached.

This is safer when the robot tends to overshoot or keep spinning.

Assumes IMU gz is in deg/s (as observed in this setup).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _key(robot_id: str, suffix: str) -> str:
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


def extract_gz_degps(payload: Any) -> Optional[float]:
    if not isinstance(payload, dict):
        return None
    v = payload.get("gz")
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


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--dir", choices=["left", "right"], default="right")
    p.add_argument("--target-deg", type=float, default=180.0)

    p.add_argument("--pulse-speed", type=float, default=0.12)
    p.add_argument("--pulse-ms", type=int, default=120)
    p.add_argument("--coast-ms", type=int, default=180)
    p.add_argument("--deadman-ms", type=int, default=300)

    p.add_argument("--hz", type=float, default=50.0)
    p.add_argument("--timeout-s", type=float, default=12.0)

    p.add_argument("--gz-max", type=float, default=720.0)
    p.add_argument("--median-n", type=int, default=5)
    p.add_argument("--stop-band-deg", type=float, default=5.0)
    p.add_argument("--safety-stop-m", type=float, default=0.05)

    args = p.parse_args(argv)

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

    def pulse() -> None:
        s = abs(float(args.pulse_speed))
        if args.dir == "right":
            publish_motor(+s, -s)
        else:
            publish_motor(-s, +s)
        time.sleep(max(0.0, int(args.pulse_ms) / 1000.0))
        publish_motor(0.0, 0.0)

    try:
        # wait for imu
        t0 = time.monotonic()
        while latest.imu is None and time.monotonic() - t0 < 2.0:
            time.sleep(0.02)
        if latest.imu is None:
            raise SystemExit("imu/state not received")

        target = float(args.target_deg)
        progressed = 0.0
        start = time.monotonic()
        dt = 1.0 / max(1.0, float(args.hz))
        gz_hist: list[float] = []

        print(
            f"[pulse-turn] dir={args.dir} target={target:.1f}deg pulse_speed={args.pulse_speed} pulse_ms={args.pulse_ms} coast_ms={args.coast_ms}"
        )

        while True:
            now = time.monotonic()
            if now - start > float(args.timeout_s):
                print("[pulse-turn] timeout -> stop")
                break

            mr = lidar_min_range(latest.scan)
            if mr != float("inf") and mr < float(args.safety_stop_m):
                print(f"[pulse-turn] safety stop: min_range={mr:.2f}m")
                break

            err = target - progressed
            if err <= float(args.stop_band_deg):
                print("[pulse-turn] reached target -> stop")
                break

            # one pulse
            pulse()

            # coast and integrate during coast window
            t_end = time.monotonic() + max(0.0, int(args.coast_ms) / 1000.0)
            last_t = time.monotonic()
            ddeg = 0.0
            while time.monotonic() < t_end:
                gz = extract_gz_degps(latest.imu)
                if gz is not None:
                    gz_dir = dir_sign * float(gz)
                    gz_dir = max(-float(args.gz_max), min(float(args.gz_max), gz_dir))
                    gz_hist.append(gz_dir)
                    n = max(1, int(args.median_n))
                    if len(gz_hist) > n:
                        gz_hist = gz_hist[-n:]
                    gz_med = sorted(gz_hist)[len(gz_hist) // 2]
                    if gz_med < 0:
                        gz_med = 0.0
                    t = time.monotonic()
                    dt_i = max(0.0, min(0.05, t - last_t))
                    last_t = t
                    ddeg += gz_med * dt_i
                time.sleep(dt)

            progressed += ddeg
            print(f"[pulse-turn] prog={progressed:6.1f}deg (+{ddeg:4.1f}) err={target-progressed:6.1f}deg min_range={mr:.2f}m")

            # adapt: when close, shorten pulse
            if target - progressed < 40:
                args.pulse_ms = max(60, int(args.pulse_ms * 0.8))
                args.pulse_speed = max(0.08, float(args.pulse_speed) * 0.9)

        stop(repeat=8)
        return 0

    finally:
        try:
            stop(repeat=4)
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


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
