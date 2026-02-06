#!/usr/bin/env python3
"""Turn by angle using IMU + LiDAR fused delta estimation.

Background
- IMU gz integration is fast but can drift/spike and was asymmetric in practice.
- LiDAR scan matching can provide a more absolute rotation cue (when the scene is
  not symmetric), but is noisy/slow and may fail in feature-poor environments.

This script uses pulse-based turning and, after each pulse, estimates the delta
angle during the settle window from:
- IMU: integrate gz (deg/s)
- LiDAR: circular shift correlation between two scan profiles
Then fuses them:
  dtheta = (1-alpha)*dtheta_imu + alpha*dtheta_lidar

Assumptions
- IMU payload: top-level 'gz' in deg/s.
- LiDAR payload: {seq, ts_ms, points:[{angle_rad, range_m, intensity}, ...]}

Safety
- Always sends repeated stop at exit.
- Timeout and max pulses.

Example
  python scripts/turn_fuse_imu_lidar.py \
    --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 \
    --dir right --target-deg 180
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

# Optional plotting (installed during this session)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


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


def extract_gz_degps(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("gz")
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
        # map angle [-pi, pi) to [0, bins)
        aa = float(a)
        # normalize
        aa = (aa + math.pi) % (2 * math.pi) - math.pi
        idx = int(((aa + math.pi) / (2 * math.pi)) * bins)
        if 0 <= idx < bins:
            # keep min range per bin (more stable around edges/occlusion)
            prev = prof[idx]
            if math.isnan(prev) or rr < prev:
                prof[idx] = rr

    # If too sparse, ignore
    if np.isfinite(prof).sum() < max(20, bins // 40):
        return None
    return prof


def circular_shift_corr(
    a: np.ndarray,
    b: np.ndarray,
    *,
    max_shift_bins: int,
    prefer_shift_bins: int = 0,
) -> Tuple[Optional[int], float]:
    """Find shift s (in bins) so that a aligns with b rolled by s.

    Returns (best_shift, best_score). Score is normalized dot-product over valid bins.
    """

    if a.shape != b.shape:
        raise ValueError("profile shape mismatch")

    bins = a.shape[0]
    valid_a = np.isfinite(a)
    valid_b = np.isfinite(b)

    best_s: Optional[int] = None
    best_score = -1e9

    # Pre-center by median to reduce DC bias
    a0 = a.copy()
    b0 = b.copy()
    if np.isfinite(a0).any():
        a0[valid_a] = a0[valid_a] - np.nanmedian(a0)
    if np.isfinite(b0).any():
        b0[valid_b] = b0[valid_b] - np.nanmedian(b0)

    # Search in window around prefer
    lo = int(max(-max_shift_bins, prefer_shift_bins - max_shift_bins))
    hi = int(min(+max_shift_bins, prefer_shift_bins + max_shift_bins))

    for s in range(lo, hi + 1):
        br = np.roll(b0, s)
        vb = np.roll(valid_b, s)
        v = valid_a & vb
        n = int(v.sum())
        if n < max(30, bins // 30):
            continue
        aa = a0[v]
        bb = br[v]
        # normalized correlation
        denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
        if denom <= 1e-9:
            continue
        score = float(np.dot(aa, bb) / denom)
        if score > best_score:
            best_score = score
            best_s = s

    return best_s, float(best_score)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--dir", choices=["left", "right"], default="right")
    p.add_argument("--target-deg", type=float, default=180.0)

    p.add_argument("--strong-speed", type=float, default=0.08)
    p.add_argument("--strong-ms", type=int, default=80)
    p.add_argument("--weak-speed", type=float, default=0.06)
    p.add_argument("--weak-ms", type=int, default=50)
    p.add_argument("--strong-until-deg", type=float, default=120.0)

    p.add_argument("--deadman-ms", type=int, default=300)

    p.add_argument("--settle-gz", type=float, default=5.0)
    p.add_argument("--settle-hold-ms", type=int, default=600)
    p.add_argument("--max-settle-s", type=float, default=2.0)

    p.add_argument("--hz", type=float, default=50.0)
    p.add_argument("--timeout-s", type=float, default=40.0)
    p.add_argument("--max-pulses", type=int, default=40)
    p.add_argument("--stop-band-deg", type=float, default=6.0)

    # LiDAR matching
    p.add_argument("--lidar-bins", type=int, default=720)
    p.add_argument("--lidar-range-min", type=float, default=0.05)
    p.add_argument("--lidar-range-max", type=float, default=6.0)
    p.add_argument("--lidar-max-shift-deg", type=float, default=45.0)
    p.add_argument("--alpha", type=float, default=0.2, help="fusion weight for lidar (0..1)")
    p.add_argument("--min-lidar-score", type=float, default=0.25)

    # logging / plotting
    p.add_argument("--log-csv", type=Path, default=None, help="write per-pulse log CSV")
    p.add_argument("--plot-png", type=Path, default=None, help="write plot PNG (requires matplotlib)")

    args = p.parse_args(argv)

    dir_sign = +1.0 if args.dir == "right" else -1.0

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

    pub_motor = sess.declare_publisher(_key(str(args.robot_id), "motor/cmd"))
    sub_imu = sess.declare_subscriber(_key(str(args.robot_id), "imu/state"), on_imu)
    sub_lidar = sess.declare_subscriber(_key(str(args.robot_id), "lidar/scan"), on_lidar)

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

    def stop(repeat: int = 10) -> None:
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

    def wait_data() -> None:
        t0 = time.monotonic()
        while (latest.imu is None or latest.lidar is None) and time.monotonic() - t0 < 3.0:
            time.sleep(0.02)

    try:
        wait_data()
        if latest.imu is None:
            raise SystemExit("imu/state not received")
        if latest.lidar is None:
            raise SystemExit("lidar/scan not received")

        progressed = 0.0
        t_start = time.monotonic()
        pulses = 0

        # per-pulse log: t_s, pulse_i, err_before, ddeg_imu, ddeg_lidar, score, ddeg_fused, progressed
        log_rows: list[tuple[float, int, float, float, float, float, float, float]] = []

        print(
            f"[fuse-turn] dir={args.dir} target={args.target_deg} alpha={args.alpha} lidar_bins={args.lidar_bins}"
        )

        while True:
            if time.monotonic() - t_start > float(args.timeout_s):
                print("[fuse-turn] timeout -> stop")
                break
            if pulses >= int(args.max_pulses):
                print("[fuse-turn] max_pulses -> stop")
                break

            err = float(args.target_deg) - progressed
            if err <= float(args.stop_band_deg):
                print("[fuse-turn] reached target -> stop")
                break

            use_strong = err > float(args.strong_until_deg)
            spd = float(args.strong_speed) if use_strong else float(args.weak_speed)
            ms = int(args.strong_ms) if use_strong else int(args.weak_ms)

            # Snapshot lidar at start of interval
            scan0 = latest.lidar
            prof0 = None
            if scan0:
                prof0 = lidar_profile(scan0, bins=int(args.lidar_bins), r_min=float(args.lidar_range_min), r_max=float(args.lidar_range_max))

            pulses += 1
            pulse(spd, ms)

            # Integrate IMU until settled (or deadline)
            settle_deadline = time.monotonic() + float(args.max_settle_s)
            last_t = time.monotonic()
            ddeg_imu = 0.0
            settled_since: Optional[float] = None

            while time.monotonic() < settle_deadline:
                gz = extract_gz_degps(latest.imu)
                if gz is None:
                    time.sleep(dt)
                    continue

                now = time.monotonic()
                dt_i = max(0.0, min(0.05, now - last_t))
                last_t = now

                # integrate only commanded direction
                gz_dir = dir_sign * float(gz)
                if gz_dir > 0:
                    ddeg_imu += gz_dir * dt_i

                ok = abs(float(gz)) <= float(args.settle_gz)
                if ok:
                    if settled_since is None:
                        settled_since = now
                else:
                    settled_since = None

                if settled_since is not None and (now - settled_since) * 1000.0 >= float(args.settle_hold_ms):
                    break

                time.sleep(dt)

            # LiDAR delta for the same interval (best-effort)
            ddeg_lidar: Optional[float] = None
            lidar_score = 0.0
            scan1 = latest.lidar
            prof1 = None
            if scan1:
                prof1 = lidar_profile(scan1, bins=int(args.lidar_bins), r_min=float(args.lidar_range_min), r_max=float(args.lidar_range_max))

            if prof0 is not None and prof1 is not None:
                bins = int(args.lidar_bins)
                max_shift_bins = int((float(args.lidar_max_shift_deg) / 360.0) * bins)
                prefer_bins = int((float(ddeg_imu) / 360.0) * bins)
                s, lidar_score = circular_shift_corr(prof0, prof1, max_shift_bins=max_shift_bins, prefer_shift_bins=prefer_bins)
                if s is not None and lidar_score >= float(args.min_lidar_score):
                    # Shift direction: make it positive in commanded direction using dir_sign
                    shift_deg = (float(s) / bins) * 360.0
                    ddeg_lidar = max(0.0, dir_sign * shift_deg)

            alpha = float(args.alpha)
            ddeg_lidar_used = float(ddeg_lidar) if ddeg_lidar is not None else float("nan")

            if ddeg_lidar is None:
                ddeg = ddeg_imu
                src = "imu"
            else:
                ddeg = (1.0 - alpha) * ddeg_imu + alpha * float(ddeg_lidar)
                src = f"fuse(score={lidar_score:.2f})"

            progressed += float(ddeg)
            t_rel = time.monotonic() - t_start
            log_rows.append(
                (
                    float(t_rel),
                    int(pulses),
                    float(err),
                    float(ddeg_imu),
                    float(ddeg_lidar_used),
                    float(lidar_score),
                    float(ddeg),
                    float(progressed),
                )
            )

            print(
                f"[fuse-turn] pulse={pulses:02d} prog={progressed:6.1f} (+{ddeg:4.1f}) err={float(args.target_deg)-progressed:6.1f} src={src}"
            )

        stop(repeat=12)

        # write logs
        if args.log_csv is not None:
            import csv

            csv_path = Path(args.log_csv).resolve()
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow([
                    "t_s",
                    "pulse_i",
                    "err_before_deg",
                    "ddeg_imu",
                    "ddeg_lidar",
                    "lidar_score",
                    "ddeg_fused",
                    "progress_deg",
                ])
                w.writerows(log_rows)
            print(f"[fuse-turn] wrote csv: {csv_path}")

        if args.plot_png is not None:
            if plt is None:
                print("[fuse-turn] matplotlib not available; skip plot")
            else:
                png_path = Path(args.plot_png).resolve()
                png_path.parent.mkdir(parents=True, exist_ok=True)

                ts = [r[0] for r in log_rows]
                d_imu = [r[3] for r in log_rows]
                d_lid = [r[4] for r in log_rows]
                scores = [r[5] for r in log_rows]
                prog = [r[7] for r in log_rows]

                fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
                ax[0].plot(ts, d_imu, label="ddeg_imu", marker="o")
                ax[0].plot(ts, d_lid, label="ddeg_lidar", marker="o")
                ax[0].set_ylabel("deg / pulse")
                ax[0].grid(True, alpha=0.3)
                ax[0].legend(loc="upper right")

                ax[1].plot(ts, scores, label="lidar_score", marker="o")
                ax[1].axhline(float(args.min_lidar_score), color="gray", linestyle="--", linewidth=1)
                ax[1].set_ylabel("score")
                ax[1].set_ylim(-0.05, 1.05)
                ax[1].grid(True, alpha=0.3)
                ax[1].legend(loc="lower right")

                ax[2].plot(ts, prog, label="progress_deg", linewidth=2)
                ax[2].axhline(float(args.target_deg), color="r", linestyle="--", linewidth=1, label="target")
                ax[2].set_xlabel("time (s)")
                ax[2].set_ylabel("deg")
                ax[2].grid(True, alpha=0.3)
                ax[2].legend(loc="lower right")

                fig.suptitle(f"Fuse turn log ({args.dir} target={args.target_deg} alpha={args.alpha})")
                fig.tight_layout()
                fig.savefig(png_path, dpi=150)
                print(f"[fuse-turn] wrote png: {png_path}")

        return 0

    finally:
        try:
            stop(repeat=6)
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


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
