#!/usr/bin/env python3
from __future__ import annotations

"""
Remote Zenoh control/subscription tool for this repository.

Usage and Zenoh connection configuration examples are documented in:
  doc/remote_pubsub/zenoh_remote_pubsub.md
"""

import argparse
import json
import math
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional


def _apply_connect_overrides(cfg, mode: str, connect_endpoints: list[str]):
    if mode:
        cfg.insert_json5("mode", json.dumps(mode))
    if connect_endpoints:
        cfg.insert_json5("connect/endpoints", json.dumps(connect_endpoints))
    return cfg


def _build_session_opener(
    *, config_path: Optional[Path], mode: str, connect_endpoints: list[str]
):
    import zenoh  # provided by `pip install eclipse-zenoh`

    if config_path is not None and not config_path.exists():
        raise SystemExit(
            f"zenoh config not found: {config_path}\n"
            "Create it (see doc/remote_pubsub/zenoh_remote_pubsub.md) or omit --zenoh-config to use defaults."
        )

    if config_path:
        cfg = zenoh.Config.from_file(str(config_path))
    else:
        try:
            cfg = zenoh.Config.from_env()
        except Exception:
            cfg = zenoh.Config()

    if connect_endpoints:
        cfg = _apply_connect_overrides(cfg, mode, connect_endpoints)

    def _opener() -> Any:
        try:
            return zenoh.open(cfg)
        except Exception as e:
            raise SystemExit(f"failed to open zenoh session: {e}") from e

    return _opener


def _key(robot_id: str, suffix: str) -> str:
    if not robot_id or "/" in robot_id:
        raise SystemExit("robot_id must be non-empty and must not contain '/'")
    return f"dmc_robo/{robot_id}/{suffix}"


def cmd_motor(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "motor/cmd")
    session = args.open_session()
    pub = session.declare_publisher(key)

    interval_s = 1.0 / args.hz if args.hz > 0 else 0.05
    end_t = time.monotonic() + args.duration_s
    seq = 0

    try:
        while time.monotonic() < end_t:
            payload = {
                "v_l": args.v_l,
                "v_r": args.v_r,
                "unit": args.unit,
                "deadman_ms": args.deadman_ms,
                "seq": seq,
                "ts_ms": int(time.time() * 1000),
            }
            pub.put(json.dumps(payload).encode("utf-8"))
            seq += 1
            time.sleep(interval_s)
    finally:
        session.close()
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "motor/cmd")
    session = args.open_session()
    pub = session.declare_publisher(key)

    try:
        for i in range(args.count):
            payload = {
                "v_l": 0.0,
                "v_r": 0.0,
                "unit": args.unit,
                "deadman_ms": args.deadman_ms,
                "seq": i,
                "ts_ms": int(time.time() * 1000),
            }
            pub.put(json.dumps(payload).encode("utf-8"))
            time.sleep(0.05)
    finally:
        session.close()
    return 0


def cmd_oled(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "oled/cmd")
    session = args.open_session()
    pub = session.declare_publisher(key)
    try:
        payload = {"text": args.text, "ts_ms": int(time.time() * 1000)}
        pub.put(json.dumps(payload).encode("utf-8"))
        time.sleep(0.1)
    finally:
        session.close()
    return 0


def _mono1_buf_len(width: int, height: int) -> int:
    if width <= 0 or height <= 0 or (height % 8) != 0:
        raise SystemExit("width/height must be > 0 and height must be a multiple of 8")
    return (width * height) // 8


def _image_path_to_mono1(path: Path, *, width: int, height: int, invert: bool) -> bytes:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except Exception as e:
        raise SystemExit("pillow is required for --image (pip install pillow)") from e

    img = Image.open(path).convert("L")
    if invert:
        img = ImageOps.invert(img)
    img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
    img = img.convert("1")

    expected = _mono1_buf_len(width, height)
    buf = bytearray(expected)
    px = img.load()
    for y in range(height):
        page = y // 8
        bit = y % 8
        base = page * width
        for x in range(width):
            if px[x, y]:
                buf[base + x] |= 1 << bit
    return bytes(buf)


def cmd_oled_image_mono1(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "oled/image/mono1")
    session = args.open_session()
    pub = session.declare_publisher(key)

    width = int(args.width)
    height = int(args.height)
    expected = _mono1_buf_len(width, height)

    if args.bin:
        payload = Path(args.bin).read_bytes()
    else:
        payload = _image_path_to_mono1(Path(args.image), width=width, height=height, invert=bool(args.invert))

    if len(payload) != expected:
        raise SystemExit(f"invalid payload size: got={len(payload)} expected={expected} ({width}x{height})")

    try:
        pub.put(payload)
        time.sleep(0.1)
    finally:
        session.close()
    return 0


def _decode_json_payload(sample: Any) -> Any:
    raw = sample.payload.to_bytes()
    return json.loads(raw.decode("utf-8"))


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        raise ValueError("empty values")
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f]) + (float(sorted_vals[c]) - float(sorted_vals[f])) * (k - f)


def _summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    vals = sorted(float(v) for v in values)
    avg = sum(vals) / len(vals)
    return {
        "count": float(len(vals)),
        "min": float(vals[0]),
        "avg": float(avg),
        "p50": float(_percentile(vals, 50)),
        "p95": float(_percentile(vals, 95)),
        "max": float(vals[-1]),
    }


def _print_summary(label: str, values: list[float]) -> None:
    stats = _summarize(values)
    if not stats:
        print(f"{label}: no samples")
        return
    print(
        f"{label}: count={int(stats['count'])} min={stats['min']:.1f} avg={stats['avg']:.1f} "
        f"p50={stats['p50']:.1f} p95={stats['p95']:.1f} max={stats['max']:.1f}"
    )


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _plot_latency(samples: list[dict[str, Any]], *, title: str | None, out_path: Path | None, show: bool) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        raise SystemExit("matplotlib is required for --plot/--plot-out (pip install matplotlib)") from e

    if not samples:
        print("no samples to plot")
        return

    xs: list[float] = []
    read_ms: list[float] = []
    pipeline: list[float] = []
    start_to_publish: list[float] = []
    publish_to_remote: list[float] = []
    for idx, sample in enumerate(samples):
        seq = sample.get("seq")
        xs.append(float(seq) if seq is not None else float(idx))
        read_val = sample.get("read_ms")
        pipeline_val = sample.get("pipeline_ms")
        start_to_publish_val = sample.get("start_to_publish_ms")
        publish_to_remote_val = sample.get("publish_to_remote_ms")
        read_num = float(read_val) if read_val is not None else math.nan
        pipeline_num = float(pipeline_val) if pipeline_val is not None else math.nan
        start_num = float(start_to_publish_val) if start_to_publish_val is not None else math.nan
        publish_remote_num = (
            float(publish_to_remote_val) if publish_to_remote_val is not None else math.nan
        )
        read_ms.append(read_num)
        pipeline.append(pipeline_num)
        start_to_publish.append(start_num)
        publish_to_remote.append(publish_remote_num)

    fig, ax = plt.subplots()
    stack_read = [0.0 if math.isnan(v) else v for v in read_ms]
    stack_pipeline = [0.0 if math.isnan(v) else v for v in pipeline]
    stack_publish_remote = [0.0 if math.isnan(v) else v for v in publish_to_remote]
    series = [stack_read, stack_pipeline]
    labels = ["read_ms", "pipeline_ms"]
    if any(v > 0 for v in stack_publish_remote):
        series.append(stack_publish_remote)
        labels.append("publish_to_remote_ms")
    if any(v > 0 for v in stack_read) or any(v > 0 for v in stack_pipeline) or any(v > 0 for v in stack_publish_remote):
        ax.stackplot(xs, series, labels=labels, alpha=0.5)
    if any(not math.isnan(v) for v in start_to_publish):
        ax.plot(xs, start_to_publish, label="start_to_publish_ms", color="black", linewidth=1.2)
    ax.set_xlabel("seq")
    ax.set_ylabel("ms")
    ax.grid(True, linestyle="--", alpha=0.4)
    if title:
        ax.set_title(title)
    ax.legend()

    if out_path:
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"saved plot: {out_path}")
    if show:
        plt.show()


def cmd_imu(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "imu/state")
    session = args.open_session()

    def on_sample(sample: Any) -> None:
        try:
            print(json.dumps(_decode_json_payload(sample), ensure_ascii=False))
        except Exception as e:
            print(f"decode failed: {e}")

    sub = session.declare_subscriber(key, on_sample)
    try:
        input("subscribing imu... press Enter to quit\n")
    finally:
        sub.undeclare()
        session.close()
    return 0


def cmd_motor_telemetry(args: argparse.Namespace) -> int:
    key = _key(args.robot_id, "motor/telemetry")
    session = args.open_session()

    def on_sample(sample: Any) -> None:
        try:
            print(json.dumps(_decode_json_payload(sample), ensure_ascii=False))
        except Exception as e:
            print(f"decode failed: {e}")

    sub = session.declare_subscriber(key, on_sample)
    try:
        input("subscribing motor telemetry... press Enter to quit\n")
    finally:
        sub.undeclare()
        session.close()
    return 0


def cmd_camera(args: argparse.Namespace) -> int:
    key_img = _key(args.robot_id, "camera/image/jpeg")
    key_meta = _key(args.robot_id, "camera/meta")
    session = args.open_session()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    state: dict[str, Any] = {"seq": None}

    def on_meta(sample: Any) -> None:
        try:
            meta = _decode_json_payload(sample)
            state["seq"] = meta.get("seq")
            if args.print_meta:
                print("meta:", json.dumps(meta, ensure_ascii=False))
        except Exception:
            return

    def on_img(sample: Any) -> None:
        jpg = sample.payload.to_bytes()
        seq = state.get("seq")
        name = out_dir / f"frame_{seq if seq is not None else int(time.time()*1000)}.jpg"
        name.write_bytes(jpg)
        print(f"saved: {name} ({len(jpg)} bytes)")

    sub_meta = session.declare_subscriber(key_meta, on_meta)
    sub_img = session.declare_subscriber(key_img, on_img)
    try:
        input("subscribing camera... press Enter to quit\n")
    finally:
        sub_img.undeclare()
        sub_meta.undeclare()
        session.close()
    return 0


def cmd_camera_latency(args: argparse.Namespace) -> int:
    key_meta = _key(args.robot_id, "camera/meta")
    session = args.open_session()

    samples: list[dict[str, Any]] = []
    lock = threading.Lock()
    stop_event = threading.Event()

    def on_meta(sample: Any) -> None:
        try:
            meta = _decode_json_payload(sample)
        except Exception:
            return

        # 受信時刻（publish->remote の推定に使用）
        recv_ts_ms = int(time.time() * 1000)
        capture_ts_ms = _to_int(meta.get("capture_ts_ms"))
        publish_ts_ms = _to_int(meta.get("publish_ts_ms"))
        capture_start_mono_ms = _to_int(meta.get("capture_start_mono_ms"))
        publish_mono_ms = _to_int(meta.get("publish_mono_ms"))
        pipeline_ms = _to_float(meta.get("pipeline_ms"))
        read_ms = _to_float(meta.get("read_ms"))
        publish_to_remote_ms = None
        if publish_ts_ms is not None:
            publish_to_remote_ms = float(recv_ts_ms - publish_ts_ms)
        start_to_publish_ms = None
        if read_ms is not None and pipeline_ms is not None:
            start_to_publish_ms = read_ms + pipeline_ms
        elif capture_start_mono_ms is not None and publish_mono_ms is not None:
            start_to_publish_ms = float(publish_mono_ms - capture_start_mono_ms)

        entry = {
            "seq": _to_int(meta.get("seq")),
            "capture_ts_ms": capture_ts_ms,
            "publish_ts_ms": publish_ts_ms,
            "recv_ts_ms": recv_ts_ms,
            "read_ms": read_ms,
            "pipeline_ms": pipeline_ms,
            "publish_to_remote_ms": publish_to_remote_ms,
            "start_to_publish_ms": start_to_publish_ms,
        }

        with lock:
            samples.append(entry)
            sample_count = len(samples)

        if args.print_each:
            print(
                "seq={seq} read_ms={read_ms} pipeline_ms={pipeline_ms} "
                "start_to_publish_ms={start_to_publish_ms} publish_to_remote_ms={publish_to_remote_ms} "
                "publish_ts_ms={publish_ts_ms} recv_ts_ms={recv_ts_ms}".format(**entry)
            )

        if args.max_samples > 0 and sample_count >= args.max_samples:
            stop_event.set()

    sub = session.declare_subscriber(key_meta, on_meta)
    try:
        if args.duration_s > 0:
            deadline = time.monotonic() + args.duration_s
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.1)
        else:
            def _wait_input() -> None:
                input("subscribing camera latency... press Enter to quit\n")
                stop_event.set()

            threading.Thread(target=_wait_input, daemon=True).start()
            while not stop_event.is_set():
                time.sleep(0.1)
    finally:
        sub.undeclare()
        session.close()

    with lock:
        snapshot = list(samples)

    read_vals = [s["read_ms"] for s in snapshot if isinstance(s.get("read_ms"), (int, float))]
    pipeline_vals = [s["pipeline_ms"] for s in snapshot if isinstance(s.get("pipeline_ms"), (int, float))]
    publish_to_remote_vals = [
        s["publish_to_remote_ms"]
        for s in snapshot
        if isinstance(s.get("publish_to_remote_ms"), (int, float))
    ]
    start_to_publish_vals = [
        s["start_to_publish_ms"]
        for s in snapshot
        if isinstance(s.get("start_to_publish_ms"), (int, float))
    ]

    _print_summary("read_ms", read_vals)
    _print_summary("pipeline_ms", pipeline_vals)
    _print_summary("start_to_publish_ms", start_to_publish_vals)
    _print_summary("publish_to_remote_ms", publish_to_remote_vals)

    if args.plot or args.plot_out:
        _plot_latency(snapshot, title=args.plot_title, out_path=args.plot_out, show=bool(args.plot))

    return 0


def cmd_camera_h264(args: argparse.Namespace) -> int:
    key_video = _key(args.robot_id, "camera/video/h264")
    key_meta = _key(args.robot_id, "camera/video/h264/meta")
    session = args.open_session()

    lock = threading.Lock()
    out_fp = None
    out_path = None
    if not args.no_raw:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_fp = out_path.open("wb")
    play_state: dict[str, Optional[object]] = {"stdin": None}
    encode_state: dict[str, Optional[object]] = {"stdin": None}

    if args.play:
        ffplay = shutil.which("ffplay")
        if not ffplay:
            print("ffplay not found; install ffmpeg to use --play")
        else:
            cmd = [
                ffplay,
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-an",
                "-i",
                "pipe:0",
            ]
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                play_state["proc"] = proc
                play_state["stdin"] = proc.stdin
            except Exception as e:
                print(f"failed to start ffplay: {e}")

    if args.encode_out:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("ffmpeg not found; install ffmpeg to use --encode-out")
        else:
            encode_path = Path(args.encode_out)
            encode_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                args.encode_codec,
            ]
            if args.encode_codec == "libx264":
                cmd.extend(["-preset", "veryfast", "-tune", "zerolatency"])
            if encode_path.suffix.lower() in {".mp4", ".mov"}:
                cmd.extend(["-movflags", "+faststart"])
            cmd.append(str(encode_path))
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                encode_state["proc"] = proc
                encode_state["stdin"] = proc.stdin
            except Exception as e:
                print(f"failed to start ffmpeg: {e}")

    def on_video(sample: Any) -> None:
        payload = sample.payload.to_bytes()
        with lock:
            if out_fp:
                out_fp.write(payload)
                if args.flush:
                    out_fp.flush()
            stdin = play_state.get("stdin")
            if stdin:
                try:
                    stdin.write(payload)
                    if args.flush:
                        stdin.flush()
                except BrokenPipeError:
                    play_state["stdin"] = None
            encode_stdin = encode_state.get("stdin")
            if encode_stdin:
                try:
                    encode_stdin.write(payload)
                    if args.flush:
                        encode_stdin.flush()
                except BrokenPipeError:
                    encode_state["stdin"] = None

    def on_meta(sample: Any) -> None:
        if not args.print_meta:
            return
        try:
            meta = _decode_json_payload(sample)
            print("meta:", json.dumps(meta, ensure_ascii=False))
        except Exception:
            return

    sub_video = session.declare_subscriber(key_video, on_video)
    sub_meta = session.declare_subscriber(key_meta, on_meta)
    try:
        input("subscribing camera h264... press Enter to quit\n")
    finally:
        sub_video.undeclare()
        sub_meta.undeclare()
        session.close()
        with lock:
            if out_fp:
                out_fp.close()
            proc = play_state.get("proc")
            if isinstance(proc, subprocess.Popen):
                try:
                    proc.terminate()
                except Exception:
                    pass
            proc = encode_state.get("proc")
            if isinstance(proc, subprocess.Popen):
                try:
                    encode_stdin = encode_state.get("stdin")
                    if encode_stdin:
                        encode_stdin.close()
                    proc.wait(timeout=2.0)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
    if out_path:
        print(f"saved: {out_path}")
    if args.encode_out:
        print(f"encoded: {args.encode_out}")
    return 0


def cmd_lidar(args: argparse.Namespace) -> int:
    key_scan = _key(args.robot_id, "lidar/scan")
    key_front = _key(args.robot_id, "lidar/front")
    session = args.open_session()

    def on_front(sample: Any) -> None:
        try:
            print(json.dumps(_decode_json_payload(sample), ensure_ascii=False))
        except Exception as e:
            print(f"decode failed: {e}")

    def on_scan(sample: Any) -> None:
        try:
            payload = _decode_json_payload(sample)
        except Exception as e:
            print(f"decode failed: {e}")
            return

        if args.print_json:
            print(json.dumps(payload, ensure_ascii=False))
            return

        seq = payload.get("seq")
        ts_ms = payload.get("ts_ms")
        points = payload.get("points") or []
        try:
            n = len(points)
        except Exception:
            n = 0
        print(f"scan: seq={seq} ts_ms={ts_ms} points={n}")

        if not args.print_points:
            return

        import math

        max_points = int(args.max_points)
        for i, p in enumerate(points[:max_points]):
            try:
                angle_rad = float(p.get("angle_rad"))
                range_m = float(p.get("range_m"))
            except Exception:
                continue
            angle_deg = math.degrees(angle_rad)
            intensity = p.get("intensity")
            if intensity is None:
                print(f"  {i:04d}: angle_deg={angle_deg:8.2f} range_m={range_m:6.3f}")
            else:
                try:
                    inten = float(intensity)
                except Exception:
                    inten = intensity
                print(f"  {i:04d}: angle_deg={angle_deg:8.2f} range_m={range_m:6.3f} intensity={inten}")

    subs = []
    try:
        if args.scan:
            subs.append(session.declare_subscriber(key_scan, on_scan))
        if args.front:
            subs.append(session.declare_subscriber(key_front, on_front))
        input("subscribing lidar... press Enter to quit\n")
    finally:
        for sub in subs:
            try:
                sub.undeclare()
            except Exception:
                pass
        session.close()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Minimal remote Zenoh control tool for dmc_ai_mobility")
    p.epilog = (
        "Docs: doc/remote_pubsub/zenoh_remote_pubsub.md (how to configure --zenoh-config / --connect)."
    )
    p.add_argument("--robot-id", required=True, help="robot_id (e.g. rasp-zero-01)")
    p.add_argument(
        "--zenoh-config",
        type=Path,
        default=None,
        help="Path to a zenoh json5 config (connect/endpoints). If omitted, uses defaults.",
    )
    p.add_argument(
        "--mode",
        type=str,
        default="peer",
        help="Zenoh mode override when using --connect (default: peer).",
    )
    p.add_argument(
        "--connect",
        action="append",
        default=[],
        help='Connect endpoint override (repeatable), e.g. --connect "tcp/192.168.1.10:7447". '
        "If set, it is applied on top of defaults or --zenoh-config.",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    motor = sub.add_parser("motor", help="Publish motor/cmd for a duration")
    motor.add_argument("--v-l", type=float, required=True)
    motor.add_argument("--v-r", type=float, required=True)
    motor.add_argument("--unit", type=str, default="mps")
    motor.add_argument("--deadman-ms", type=int, default=300)
    motor.add_argument("--duration-s", type=float, default=2.0)
    motor.add_argument("--hz", type=float, default=20.0)
    motor.set_defaults(func=cmd_motor)

    stop = sub.add_parser("stop", help="Publish zero motor command a few times")
    stop.add_argument("--unit", type=str, default="mps")
    stop.add_argument("--deadman-ms", type=int, default=300)
    stop.add_argument("--count", type=int, default=5)
    stop.set_defaults(func=cmd_stop)

    oled = sub.add_parser("oled", help="Publish oled/cmd once")
    oled.add_argument("--text", type=str, required=True)
    oled.set_defaults(func=cmd_oled)

    oled_img = sub.add_parser("oled-image", help="Publish oled/image/mono1 once (raw mono1 bytes)")
    oled_img_src = oled_img.add_mutually_exclusive_group(required=True)
    oled_img_src.add_argument("--bin", type=str, default=None, help="Path to a prebuilt mono1 .bin payload")
    oled_img_src.add_argument("--image", type=str, default=None, help="Path to an input image (png/jpg/...)")
    oled_img.add_argument("--width", type=int, default=128)
    oled_img.add_argument("--height", type=int, default=32)
    oled_img.add_argument("--invert", action="store_true", help="Invert input image before mono1 conversion")
    oled_img.set_defaults(func=cmd_oled_image_mono1)

    imu = sub.add_parser("imu", help="Subscribe imu/state and print JSON")
    imu.set_defaults(func=cmd_imu)

    motor_telemetry = sub.add_parser("motor-telemetry", help="Subscribe motor/telemetry and print JSON")
    motor_telemetry.set_defaults(func=cmd_motor_telemetry)

    cam = sub.add_parser("camera", help="Subscribe camera jpeg/meta and save JPEGs")
    cam.add_argument("--out-dir", type=Path, default=Path("./camera_frames"))
    cam.add_argument("--print-meta", action="store_true")
    cam.set_defaults(func=cmd_camera)

    cam_h264 = sub.add_parser("camera-h264", help="Subscribe camera/video/h264 and save stream")
    cam_h264.add_argument("--out", type=str, default="./camera_stream.h264")
    cam_h264.add_argument("--no-raw", action="store_true", help="Do not save raw .h264 stream")
    cam_h264.add_argument("--print-meta", action="store_true")
    cam_h264.add_argument("--flush", action="store_true", help="Flush after each write")
    cam_h264.add_argument("--play", action="store_true", help="Play stream with ffplay (requires ffmpeg)")
    cam_h264.add_argument("--encode-out", type=str, default=None, help="Transcode to a file via ffmpeg")
    cam_h264.add_argument("--encode-codec", type=str, default="libx264")
    cam_h264.set_defaults(func=cmd_camera_h264)

    cam_latency = sub.add_parser("camera-latency", help="Subscribe camera/meta and report latency stats")
    cam_latency.add_argument(
        "--duration-s",
        type=float,
        default=10.0,
        help="Measurement duration in seconds (<=0 waits for Enter).",
    )
    cam_latency.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Stop after N samples (0 = unlimited).",
    )
    cam_latency.add_argument("--print-each", action="store_true", help="Print per-sample latency")
    cam_latency.add_argument("--plot", action="store_true", help="Show matplotlib graph (requires matplotlib)")
    cam_latency.add_argument("--plot-out", type=Path, default=None, help="Save graph to a file (png)")
    cam_latency.add_argument("--plot-title", type=str, default=None, help="Optional plot title")
    cam_latency.set_defaults(func=cmd_camera_latency)

    lidar = sub.add_parser("lidar", help="Subscribe lidar scan/front and print")
    lidar.add_argument("--scan", action="store_true", help="Subscribe lidar/scan (angle-wise raw values)")
    lidar.add_argument("--front", action="store_true", help="Subscribe lidar/front (summary distance)")
    lidar.add_argument("--print-json", action="store_true", help="Print scan payload as raw JSON")
    lidar.add_argument("--print-points", action="store_true", help="Print per-point angle/range from scan payload")
    lidar.add_argument("--max-points", type=int, default=100, help="Max points to print when --print-points")
    lidar.set_defaults(func=cmd_lidar)

    args = p.parse_args(argv)
    if args.cmd == "lidar" and not getattr(args, "scan", False) and not getattr(args, "front", False):
        args.front = True
    args.open_session = _build_session_opener(
        config_path=args.zenoh_config, mode=args.mode, connect_endpoints=list(args.connect)
    )
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
