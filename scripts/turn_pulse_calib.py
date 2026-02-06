#!/usr/bin/env python3
"""Turn using calibrated pulses with IMU settle-wait integration.

Fix for overshoot:
- Previously we integrated only for a fixed coast window.
- Now we integrate until rotation *settles* (|gz| <= settle_gz for settle_hold_ms),
  or until max_settle_s is reached.

This reduces "counting short" when the robot keeps spinning after a pulse.

Assumes IMU top-level 'gz' is deg/s (as observed on this robot).
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


def extract_gz(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("gz")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--dir", choices=["left", "right"], default="right")
    p.add_argument("--target-deg", type=float, default=180.0)

    # strong pulse
    p.add_argument("--strong-speed", type=float, default=0.08)
    p.add_argument("--strong-ms", type=int, default=80)

    # weak pulse
    p.add_argument("--weak-speed", type=float, default=0.06)
    p.add_argument("--weak-ms", type=int, default=50)

    p.add_argument("--deadman-ms", type=int, default=300)

    p.add_argument("--settle-gz", type=float, default=5.0)
    p.add_argument("--settle-hold-ms", type=int, default=600)
    p.add_argument("--max-settle-s", type=float, default=2.0)

    p.add_argument("--hz", type=float, default=50.0)
    p.add_argument("--timeout-s", type=float, default=25.0)
    p.add_argument("--stop-band-deg", type=float, default=6.0)

    p.add_argument("--gz-max", type=float, default=720.0)
    p.add_argument("--median-n", type=int, default=7)

    # pulse scheduling
    p.add_argument("--strong-until-deg", type=float, default=90.0, help="use strong pulse while err > this")
    p.add_argument("--flip-imu", action="store_true", help="flip sign of gz (use if direction is inverted)")

    args = p.parse_args(argv)

    dir_sign = +1.0 if args.dir == "right" else -1.0
    if args.flip_imu:
        dir_sign *= -1.0

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()
    latest = Latest()

    def on_imu(sample: Any) -> None:
        try:
            latest.imu = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    pub_motor = sess.declare_publisher(_key(str(args.robot_id), "motor/cmd"))
    sub_imu = sess.declare_subscriber(_key(str(args.robot_id), "imu/state"), on_imu)

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

    def pulse(speed: float, ms: int) -> None:
        s = abs(float(speed))
        if args.dir == "right":
            publish_motor(+s, -s)
        else:
            publish_motor(-s, +s)
        time.sleep(max(0.0, int(ms) / 1000.0))
        publish_motor(0.0, 0.0)

    dt = 1.0 / max(1.0, float(args.hz))

    try:
        # wait IMU
        t0 = time.monotonic()
        while latest.imu is None and time.monotonic() - t0 < 2.0:
            time.sleep(0.02)
        if latest.imu is None:
            raise SystemExit("imu/state not received")

        progressed = 0.0
        t_start = time.monotonic()
        gz_hist: list[float] = []

        print(
            f"[calib-turn] dir={args.dir} target={args.target_deg} stop_band={args.stop_band_deg} "
            f"settle_gz={args.settle_gz} hold_ms={args.settle_hold_ms} max_settle_s={args.max_settle_s}"
        )

        while True:
            if time.monotonic() - t_start > float(args.timeout_s):
                print("[calib-turn] timeout -> stop")
                break

            err = float(args.target_deg) - progressed
            if err <= float(args.stop_band_deg):
                print("[calib-turn] reached target -> stop")
                break

            use_strong = err > float(args.strong_until_deg)
            spd = float(args.strong_speed) if use_strong else float(args.weak_speed)
            ms = int(args.strong_ms) if use_strong else int(args.weak_ms)

            pulse(spd, ms)

            # integrate until settled (or max_settle_s)
            settle_deadline = time.monotonic() + float(args.max_settle_s)
            last_t = time.monotonic()
            ddeg = 0.0
            settled_since: Optional[float] = None

            while time.monotonic() < settle_deadline:
                gz = extract_gz(latest.imu)
                if gz is not None:
                    gz_dir = dir_sign * float(gz)
                    gz_dir = clamp(gz_dir, -float(args.gz_max), float(args.gz_max))
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

                    ok = abs(float(gz)) <= float(args.settle_gz)
                    if ok:
                        if settled_since is None:
                            settled_since = t
                    else:
                        settled_since = None

                    if settled_since is not None and (t - settled_since) * 1000.0 >= float(args.settle_hold_ms):
                        break

                time.sleep(dt)

            progressed += ddeg
            print(
                f"[calib-turn] prog={progressed:6.1f} (+{ddeg:4.1f}) err={float(args.target_deg)-progressed:6.1f} "
                f"using={'strong' if use_strong else 'weak'}"
            )

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
            sess.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
