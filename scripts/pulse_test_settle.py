#!/usr/bin/env python3
"""Send a single short turn pulse, then observe IMU gz until rotation settles.

Goal: measure how much the robot rotates per minimum pulse and how long it takes
for rotation to stop (helps tune control and detect overshoot/slip).

Assumes IMU payload has top-level 'gz' in deg/s.
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


def extract_gz_degps(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("gz")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--dir", choices=["left", "right"], default="right")
    p.add_argument("--pulse-speed", type=float, default=0.06)
    p.add_argument("--pulse-ms", type=int, default=50)
    p.add_argument("--deadman-ms", type=int, default=300)

    p.add_argument("--settle-gz", type=float, default=5.0, help="consider settled when |gz| <= this")
    p.add_argument("--settle-hold-ms", type=int, default=500, help="must stay settled this long")
    p.add_argument("--timeout-s", type=float, default=8.0)
    p.add_argument("--hz", type=float, default=50.0)

    args = p.parse_args(argv)

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()
    latest = Latest()

    def on_imu(sample: Any) -> None:
        try:
            latest.imu = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    key_imu = _key(str(args.robot_id), "imu/state")
    key_motor = _key(str(args.robot_id), "motor/cmd")

    pub_motor = sess.declare_publisher(key_motor)
    sub_imu = sess.declare_subscriber(key_imu, on_imu)

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

    def stop(repeat: int = 5) -> None:
        for _ in range(max(1, int(repeat))):
            publish_motor(0.0, 0.0)
            time.sleep(0.05)

    dt = 1.0 / max(1.0, float(args.hz))

    try:
        # wait for imu
        t0 = time.monotonic()
        while latest.imu is None and time.monotonic() - t0 < 2.0:
            time.sleep(0.02)
        if latest.imu is None:
            raise SystemExit("imu/state not received")

        s = abs(float(args.pulse_speed))
        if args.dir == "right":
            v_l, v_r = +s, -s
        else:
            v_l, v_r = -s, +s

        print(f"[pulse-test] send one pulse dir={args.dir} speed={s} ms={args.pulse_ms}")
        publish_motor(v_l, v_r)
        time.sleep(max(0.0, int(args.pulse_ms) / 1000.0))
        publish_motor(0.0, 0.0)

        # observe settle
        start = time.monotonic()
        settled_since: Optional[float] = None
        last_t = time.monotonic()
        yaw_deg = 0.0

        print(f"[pulse-test] observing until |gz|<={args.settle_gz} for {args.settle_hold_ms}ms")

        while True:
            now = time.monotonic()
            if now - start > float(args.timeout_s):
                print("[pulse-test] timeout")
                break

            gz = extract_gz_degps(latest.imu)
            if gz is None:
                time.sleep(dt)
                continue

            dt_i = max(0.0, min(0.05, now - last_t))
            last_t = now
            yaw_deg += float(gz) * dt_i

            ok = abs(gz) <= float(args.settle_gz)
            if ok:
                if settled_since is None:
                    settled_since = now
            else:
                settled_since = None

            print(f"[pulse-test] t={now-start:4.2f}s gz={gz:+7.2f} deg/s yaw~={yaw_deg:+7.1f} deg")

            if settled_since is not None:
                if (now - settled_since) * 1000.0 >= float(args.settle_hold_ms):
                    print(f"[pulse-test] settled after {now-start:.2f}s, yaw~={yaw_deg:+.1f}deg")
                    break

            time.sleep(dt)

    finally:
        stop(repeat=6)
        try:
            sub_imu.undeclare()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
