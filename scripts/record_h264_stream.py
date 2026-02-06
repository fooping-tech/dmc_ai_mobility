#!/usr/bin/env python3
"""Record raw H.264 stream from Zenoh to a .h264 file.

Subscribes to:
  dmc_robo/<robot_id>/camera/video/h264

Writes payload bytes as-is to output.

Typical usage:
  python scripts/record_h264_stream.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 --out out.h264 --duration-s 12
"""

from __future__ import annotations

import argparse
import json
import time
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


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--zenoh-config", type=Path, default=None)
    p.add_argument("--mode", default="peer")
    p.add_argument("--connect", action="append", default=[])

    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--duration-s", type=float, default=10.0)
    p.add_argument("--quiet", action="store_true")

    args = p.parse_args(argv)

    import zenoh

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()

    topic = _key(str(args.robot_id), "camera/video/h264")
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_bytes = 0
    n_chunks = 0

    f = out_path.open("wb")

    def on_h264(sample: Any) -> None:
        nonlocal n_bytes, n_chunks
        try:
            b = sample.payload.to_bytes()
        except Exception:
            return
        if not b:
            return
        try:
            f.write(b)
            n_bytes += len(b)
            n_chunks += 1
        except Exception:
            return

    sub = sess.declare_subscriber(topic, on_h264)

    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < float(args.duration_s):
            if not args.quiet and (n_chunks % 200 == 0) and n_chunks > 0:
                dt = time.monotonic() - t0
                print(f"[record_h264] {dt:.1f}s chunks={n_chunks} bytes={n_bytes}")
            time.sleep(0.01)
    finally:
        try:
            sub.undeclare()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass
        try:
            f.flush()
            f.close()
        except Exception:
            pass

    if not args.quiet:
        print(f"[record_h264] done: {out_path} chunks={n_chunks} bytes={n_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
