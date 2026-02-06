#!/usr/bin/env python3
"""Capture a single PNG frame directly from the Zenoh H.264 stream (no UI).

Subscribes to:
- dmc_robo/<robot_id>/camera/video/h264

Pipes received bytes into ffmpeg and writes one decoded frame to PNG.

Notes:
- H.264 decode may require SPS/PPS to appear in-stream; we keep feeding until
  ffmpeg produces a frame or timeout.
- Requires ffmpeg installed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
    p.add_argument("--out", type=Path, default=Path("h264_frame.png"))
    p.add_argument("--timeout-s", type=float, default=12.0)
    args = p.parse_args(argv)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found")

    import zenoh

    open_session = _build_session_opener(args.zenoh_config, str(args.mode), list(args.connect))
    sess = open_session()

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Decode a single frame to PNG and exit.
    cmd = [
        ffmpeg,
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-f",
        "h264",
        "-i",
        "pipe:0",
        "-frames:v",
        "1",
        "-y",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    topic = _key(str(args.robot_id), "camera/video/h264")
    done = {"ok": False}

    def on_h264(sample: Any) -> None:
        if done["ok"]:
            return
        try:
            b = sample.payload.to_bytes()
        except Exception:
            return
        if not b:
            return
        try:
            if proc.stdin:
                proc.stdin.write(b)
        except Exception:
            return

    sub = sess.declare_subscriber(topic, on_h264)

    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < float(args.timeout_s):
            rc = proc.poll()
            if rc is not None:
                # ffmpeg exited (hopefully after writing 1 frame)
                if out_path.exists() and out_path.stat().st_size > 0:
                    done["ok"] = True
                    return 0
                return 2
            time.sleep(0.05)

        return 3

    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            sub.undeclare()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(list(__import__("sys").argv[1:])))
