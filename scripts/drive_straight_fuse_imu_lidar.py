#!/usr/bin/env python3
"""Drive forward while keeping heading straight using IMU + LiDAR.

Problem
- At very low speeds, one wheel may not start turning -> the robot yaws and does
  not go straight.

Approach
- Estimate heading change (deg) from:
  - IMU: integrate gz (deg/s)
  - LiDAR: scan profile shift correlation (as in turn_fuse_imu_lidar.py)
- Fuse them with complementary weight alpha (LiDAR weight).
- Apply a simple P controller on heading error to adjust left/right wheel speeds.

Keys
- IMU:  dmc_robo/<robot_id>/imu/state (gz)
- LiDAR: dmc_robo/<robot_id>/lidar/scan (points)
- LiDAR front summary (optional safety): dmc_robo/<robot_id>/lidar/front (distance_m)
- Motor cmd: dmc_robo/<robot_id>/motor/cmd

Example
  python scripts/drive_straight_fuse_imu_lidar.py \
    --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 \
    --v 0.08 --duration-s 3.0
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np


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
    lidar: Optional[dict[str, Any]] = None
    front: Optional[dict[str, Any]] = None


def extract_gz_degps(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("gz")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def extract_front_m(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("distance_m")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def lidar_profile(scan: dict[str, Any], *, bins: int, r_min: float, r_max: float) -> Optional[np.ndarray]:
    pts = scan.get("points")
    if not isinstance(pts, list) or not pts:
        return None

    prof = np.full((bins,), np.nan, dtype=np.float32)
    for p in pts:
        if not isinstance(p, dict):
            continue
        a = p.get("angle_rad")
        r = p.get("range_m")
        if not isinstance(a, (int, float)) or not isinstance(r, (int, float)):
            continue
        rr = float(r)
        if not (r_min <= rr <= r_max):
            continue
        aa = float(a)
        aa = (aa + math.pi) % (2 * math.pi) - math.pi
        idx = int(((aa + math.pi) / (2 * math.pi)) * bins)
        if 0 <= idx < bins:
            prev = prof[idx]
            if math.isnan(prev) or rr < prev:
                prof[idx] = rr

    if np.isfinite(prof).sum() < max(30, bins // 30):
        return None
    return prof


def circular_shift_corr(a: np.ndarray, b: np.ndarray, *, max_shift_bins: int, prefer_shift_bins: int = 0) -> Tuple[Optional[int], float]:
    if a.shape != b.shape:
        raise ValueError("profile shape mismatch")

    bins = a.shape[0]
    valid_a = np.isfinite(a)
    valid_b = np.isfinite(b)

    best_s: Optional[int] = None
    best_score = -1e9

    a0 = a.copy()
    b0 = b.copy()
    if np.isfinite(a0).any():
        a0[valid_a] = a0[valid_a] - np.nanmedian(a0)
    if np.isfinite(b0).any():
        b0[valid_b] = b0[valid_b] - np.nanmedian(b0)

    lo = int(max(-max_shift_bins, prefer_shift_bins - max_shift_bins))
    hi = int(min(+max_shift_bins, prefer_shift_bins + max_shift_bins))

    for s in range(lo, hi + 1):
        br = np.roll(b0, s)
        vb = np.roll(valid_b, s)
        v = valid_a & vb
        n = int(v.sum())
        if n < max(40, bins // 20):
            continue
        aa = a0[v]
        bb = br[v]
        denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
        if denom <= 1e-9:
            continue
        score = float(np.dot(aa, bb) / denom)
        if score > best_score:
            best_score = score
            best_s = s

    return best_s, float(best_score)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--v", type=float, default=0.08, help="base forward speed (m/s)")
    p.add_argument("--duration-s", type=float, default=3.0)
    p.add_argument("--hz", type=float, default=20.0)

    p.add_argument("--deadman-ms", type=int, default=300)

    # Controller (PID on heading)
    p.add_argument("--kp", type=float, default=0.0020, help="P gain (delta_v per deg heading error)")
    p.add_argument("--ki", type=float, default=0.0000, help="I gain (delta_v per deg*s)")
    p.add_argument("--kd", type=float, default=0.0000, help="D gain (delta_v per deg/s)")
    p.add_argument("--delta-max", type=float, default=0.06, help="max differential speed (m/s)")
    p.add_argument("--v-min", type=float, default=0.08, help="minimum wheel speed to avoid one-wheel stall")
    p.add_argument("--kick-ms", type=int, default=120, help="initial straight kick duration (ms)")
    p.add_argument("--kick-v", type=float, default=0.18, help="initial straight kick speed (m/s)")

    # Fusion
    p.add_argument("--alpha", type=float, default=0.4, help="LiDAR weight 0..1")
    p.add_argument("--lidar-bins", type=int, default=720)
    p.add_argument("--lidar-range-min", type=float, default=0.05)
    p.add_argument("--lidar-range-max", type=float, default=6.0)
    p.add_argument("--lidar-max-shift-deg", type=float, default=10.0, help="per-cycle shift search window")
    p.add_argument("--min-lidar-score", type=float, default=0.25)

    # Safety: stop if too close ahead (use lidar/front)
    p.add_argument("--stop-front-m", type=float, default=0.20, help="stop if front distance <= this (m)")

    # Logging
    p.add_argument("--log-csv", type=Path, default=None)

    args = p.parse_args(argv)

    import zenoh

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()

    latest = Latest()

    def on_imu(sample: Any) -> None:
        try:
            latest.imu = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    def on_lidar(sample: Any) -> None:
        try:
            latest.lidar = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    def on_front(sample: Any) -> None:
        try:
            latest.front = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    pub_motor = sess.declare_publisher(_key(str(args.robot_id), "motor/cmd"))
    sub_imu = sess.declare_subscriber(_key(str(args.robot_id), "imu/state"), on_imu)
    sub_lidar = sess.declare_subscriber(_key(str(args.robot_id), "lidar/scan"), on_lidar)
    sub_front = sess.declare_subscriber(_key(str(args.robot_id), "lidar/front"), on_front)

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

    def stop(repeat: int = 8) -> None:
        for _ in range(max(1, int(repeat))):
            publish_motor(0.0, 0.0)
            time.sleep(0.05)

    dt = 1.0 / max(1.0, float(args.hz))

    # wait initial data
    t0 = time.monotonic()
    while (latest.imu is None or latest.lidar is None) and time.monotonic() - t0 < 3.0:
        time.sleep(0.02)
    if latest.imu is None:
        raise SystemExit("imu/state not received")
    if latest.lidar is None:
        raise SystemExit("lidar/scan not received")

    heading_deg = 0.0
    i_term = 0.0
    prev_heading = 0.0

    prev_prof = lidar_profile(latest.lidar, bins=int(args.lidar_bins), r_min=float(args.lidar_range_min), r_max=float(args.lidar_range_max))
    prev_t = time.monotonic()

    log_rows: list[tuple[float, float, float, float, float, float, float, float]] = []
    # t, heading, gz, dtheta_imu, dtheta_lidar, score, v_l, v_r

    try:
        t_start = time.monotonic()

        # Kick both wheels to overcome static friction / deadband
        if int(args.kick_ms) > 0 and float(args.kick_v) > 0:
            publish_motor(float(args.kick_v), float(args.kick_v))
            time.sleep(max(0.0, int(args.kick_ms) / 1000.0))

        while True:
            now = time.monotonic()
            if now - t_start >= float(args.duration_s):
                break

            # safety
            d_front = extract_front_m(latest.front)
            if d_front is not None and d_front <= float(args.stop_front_m):
                print(f"[straight] stop: front distance {d_front:.3f}m")
                break

            gz = extract_gz_degps(latest.imu)
            if gz is None:
                time.sleep(dt)
                continue

            dt_i = max(0.0, min(0.2, now - prev_t))
            prev_t = now

            # IMU heading increment (deg)
            dtheta_imu = float(gz) * dt_i

            # LiDAR heading increment (deg) between profiles
            dtheta_lidar = float("nan")
            score = 0.0
            prof = None
            if latest.lidar is not None:
                prof = lidar_profile(latest.lidar, bins=int(args.lidar_bins), r_min=float(args.lidar_range_min), r_max=float(args.lidar_range_max))

            if prev_prof is not None and prof is not None:
                bins = int(args.lidar_bins)
                max_shift_bins = int((float(args.lidar_max_shift_deg) / 360.0) * bins)
                prefer_bins = int((float(dtheta_imu) / 360.0) * bins)
                s, score = circular_shift_corr(prev_prof, prof, max_shift_bins=max_shift_bins, prefer_shift_bins=prefer_bins)
                if s is not None and score >= float(args.min_lidar_score):
                    dtheta_lidar = (float(s) / bins) * 360.0

            # fuse increment
            alpha = float(args.alpha)
            if math.isnan(dtheta_lidar):
                dtheta = dtheta_imu
            else:
                dtheta = (1.0 - alpha) * dtheta_imu + alpha * float(dtheta_lidar)

            heading_deg += dtheta

            # PID control on heading_deg to steer back to 0
            # If heading_deg > 0 (yawing right), steer left => v_l > v_r.
            # error = -heading
            err_h = -heading_deg
            # integrate with anti-windup via clamp at output stage
            i_term += err_h * dt_i
            # derivative (deg/s)
            d_term = 0.0
            if dt_i > 1e-3:
                d_term = (heading_deg - prev_heading) / dt_i
            prev_heading = heading_deg

            delta = float(args.kp) * err_h + float(args.ki) * i_term - float(args.kd) * d_term
            delta = clamp(delta, -float(args.delta_max), +float(args.delta_max))

            v_base = float(args.v)
            v_l = clamp(v_base + delta, -0.30, +0.30)
            v_r = clamp(v_base - delta, -0.30, +0.30)

            # Enforce minimum magnitude (forward) so both wheels keep spinning.
            vmin = max(0.0, float(args.v_min))
            if v_base >= 0:
                v_l = max(vmin, v_l)
                v_r = max(vmin, v_r)

            publish_motor(v_l, v_r)

            t_rel = now - t_start
            log_rows.append((t_rel, heading_deg, float(gz), float(dtheta_imu), float(dtheta_lidar), float(score), float(v_l), float(v_r)))

            if prof is not None:
                prev_prof = prof

            time.sleep(dt)

    finally:
        stop(10)
        try:
            sub_front.undeclare()
        except Exception:
            pass
        try:
            sub_lidar.undeclare()
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

    if args.log_csv is not None:
        csv_path = Path(args.log_csv).resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "heading_deg", "gz", "dtheta_imu", "dtheta_lidar", "lidar_score", "v_l", "v_r"])
            w.writerows(log_rows)
        print(f"[straight] wrote csv: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
