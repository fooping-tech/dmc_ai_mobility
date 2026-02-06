#!/usr/bin/env python3
"""Run left 180 turn (pulse+settle) while logging IMU gz and integrated progress.

Outputs:
- CSV log
- PNG plot

We treat LEFT rotation as positive progress by using gz_dir = -gz_raw.
Assumes IMU payload includes top-level 'gz' in deg/s.

Safety:
- max_pulses limit
- always stop at end
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _key(robot_id: str, suffix: str) -> str:
    return f"dmc_robo/{robot_id}/{suffix}"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def extract_gz(payload: Any) -> Optional[float]:
    if isinstance(payload, dict):
        v = payload.get("gz")
        if isinstance(v, (int, float)):
            return float(v)
    return None


@dataclass
class Latest:
    imu: Optional[dict[str, Any]] = None


def main() -> int:
    import zenoh

    robot_id = "rasp-zero-01"
    zenoh_config = Path("./zenoh_remote.json5")

    target_deg = 180.0

    # Left is weaker / asymmetric: use higher pulses, but still keep bounded.
    strong_speed, strong_ms = 0.22, 180
    weak_speed, weak_ms = 0.15, 120
    strong_until_deg = 120.0

    settle_gz = 6.0
    settle_hold_ms = 800
    max_settle_s = 2.5

    stop_band = 10.0
    deadman_ms = 300

    hz = 50.0
    gz_max = 720.0
    median_n = 7

    max_pulses = 12

    out_csv = Path("/home/fukuhala/python_ws/dmc_ai_mobility/left180_imu_log.csv")
    out_png = Path("/home/fukuhala/python_ws/dmc_ai_mobility/left180_imu_plot.png")

    cfg = zenoh.Config.from_file(str(zenoh_config))
    sess = zenoh.open(cfg)

    latest = Latest()

    def on_imu(sample: Any) -> None:
        try:
            latest.imu = json.loads(sample.payload.to_bytes().decode("utf-8"))
        except Exception:
            return

    pub_motor = sess.declare_publisher(_key(robot_id, "motor/cmd"))
    sub_imu = sess.declare_subscriber(_key(robot_id, "imu/state"), on_imu)

    def publish_motor(v_l: float, v_r: float) -> None:
        payload = {
            "v_l": float(v_l),
            "v_r": float(v_r),
            "unit": "mps",
            "deadman_ms": int(deadman_ms),
            "seq": int(time.time() * 1000) % 1_000_000_000,
            "ts_ms": int(time.time() * 1000),
        }
        pub_motor.put(json.dumps(payload).encode("utf-8"))

    def stop(repeat: int = 8) -> None:
        for _ in range(repeat):
            publish_motor(0.0, 0.0)
            time.sleep(0.05)

    def pulse(speed: float, ms: int) -> None:
        s = abs(float(speed))
        # left: v_l=-, v_r=+
        publish_motor(-s, +s)
        time.sleep(ms / 1000.0)
        publish_motor(0.0, 0.0)

    # wait IMU
    t0 = time.monotonic()
    while latest.imu is None and time.monotonic() - t0 < 2.0:
        time.sleep(0.02)
    if latest.imu is None:
        raise SystemExit("imu/state not received")

    dt = 1.0 / hz
    progressed = 0.0
    gz_hist: list[float] = []

    rows: list[tuple[float, float, float, float, float, int]] = []
    # t, gz_raw, gz_dir, gz_med, progressed, pulse_i

    t_start = time.monotonic()
    pulse_i = 0

    try:
        while True:
            err = target_deg - progressed
            if err <= stop_band:
                break
            if pulse_i >= max_pulses:
                break

            use_strong = err > strong_until_deg
            spd = strong_speed if use_strong else weak_speed
            ms = strong_ms if use_strong else weak_ms

            pulse_i += 1
            pulse(spd, ms)

            # integrate until settled
            settle_deadline = time.monotonic() + max_settle_s
            settled_since: Optional[float] = None
            last_t = time.monotonic()

            while time.monotonic() < settle_deadline:
                now = time.monotonic()
                gz_raw = extract_gz(latest.imu)
                if gz_raw is None:
                    time.sleep(dt)
                    continue

                # LEFT progress positive
                gz_dir = -clamp(float(gz_raw), -gz_max, +gz_max)
                gz_hist.append(gz_dir)
                if len(gz_hist) > median_n:
                    gz_hist = gz_hist[-median_n:]
                gz_med = sorted(gz_hist)[len(gz_hist) // 2]

                gz_for_int = max(0.0, gz_med)
                dt_i = max(0.0, min(0.05, now - last_t))
                last_t = now
                progressed += gz_for_int * dt_i

                t_rel = now - t_start
                rows.append((t_rel, float(gz_raw), float(gz_dir), float(gz_med), float(progressed), pulse_i))

                ok = abs(float(gz_raw)) <= settle_gz
                if ok:
                    if settled_since is None:
                        settled_since = now
                else:
                    settled_since = None

                if settled_since is not None and (now - settled_since) * 1000.0 >= settle_hold_ms:
                    break

                time.sleep(dt)

    finally:
        stop(10)
        try:
            sub_imu.undeclare()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass

    # write CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "gz_raw", "gz_dir", "gz_med", "progress_deg", "pulse_i"])
        w.writerows(rows)

    # plot
    ts = [r[0] for r in rows]
    gz_raws = [r[1] for r in rows]
    gz_meds = [r[3] for r in rows]
    prog = [r[4] for r in rows]

    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(ts, gz_raws, label="gz_raw (deg/s)", linewidth=1)
    ax[0].plot(ts, gz_meds, label="gz_med (deg/s)", linewidth=2)
    ax[0].axhline(settle_gz, color="gray", linestyle="--", linewidth=1)
    ax[0].axhline(-settle_gz, color="gray", linestyle="--", linewidth=1)
    ax[0].set_ylabel("deg/s")
    ax[0].legend(loc="upper right")
    ax[0].grid(True, alpha=0.3)

    ax[1].plot(ts, prog, label="progress_deg (left)", linewidth=2)
    ax[1].axhline(target_deg, color="r", linestyle="--", linewidth=1, label="target")
    ax[1].set_ylabel("deg")
    ax[1].set_xlabel("time (s)")
    ax[1].legend(loc="lower right")
    ax[1].grid(True, alpha=0.3)

    fig.suptitle("Left 180 turn IMU log (gz) + integrated progress")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)

    print(f"wrote: {out_csv}")
    print(f"wrote: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
