from __future__ import annotations

import argparse
import math
import sys
import time
from typing import Iterable, Optional

from dmc_ai_mobility.drivers.lidar import (
    LidarPoint,
    LidarScan,
    MockLidarDriver,
    YdLidarConfig,
    YdLidarDriver,
)


def _front_points(points: Iterable[LidarPoint], window_deg: float) -> list[float]:
    half = max(float(window_deg), 0.0) / 2.0
    dists: list[float] = []
    for p in points:
        angle_deg = math.degrees(p.angle_rad)
        if abs(angle_deg) <= half:
            dists.append(p.range_m)
    return dists


def _stat(dists: list[float], mode: str) -> Optional[float]:
    if not dists:
        return None
    if mode == "min":
        return min(dists)
    return sum(dists) / len(dists)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="YDLidar example: print front distance")
    parser.add_argument("--mock", action="store_true", help="Run without LiDAR hardware")
    parser.add_argument("--port", default="/dev/ttyAMA0", help="Serial port (default: /dev/ttyAMA0)")
    parser.add_argument("--baud", type=int, default=230400, help="Serial baudrate (default: 230400)")
    parser.add_argument("--window-deg", type=float, default=10.0, help="Front angular window in degrees")
    parser.add_argument("--stat", choices=["mean", "min"], default="mean", help="Aggregate method")
    parser.add_argument("--hz", type=float, default=20.0, help="Print rate (best-effort)")
    args = parser.parse_args(argv)

    if args.mock:
        driver = MockLidarDriver()
        print("LiDAR Running (mock) (Press Ctrl+C to stop)")
    else:
        cfg = YdLidarConfig(serial_port=args.port, serial_baudrate=args.baud)
        driver = YdLidarDriver(cfg)
        print("LiDAR Running! (Press Ctrl+C to stop)")

    period_s = 1.0 / max(float(args.hz), 1.0)
    try:
        while True:
            scan: Optional[LidarScan] = driver.read()
            if scan is not None:
                front = _front_points(scan.points, window_deg=args.window_deg)
                value = _stat(front, args.stat)
                if value is not None:
                    print(f"Front({args.stat}): {value:.3f} m  (Samples: {len(front)})")
            time.sleep(period_s)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
