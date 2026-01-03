#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dmc_ai_mobility.core.oled_bitmap import image_path_to_mono1_buffer  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an image sequence into OLED mono1 .bin frames.")
    parser.add_argument("--in-dir", type=Path, required=True, help="Input directory with images (png/jpg/...)")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for .bin frames")
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=32)
    parser.add_argument("--invert", action="store_true", help="Invert input images before conversion")
    parser.add_argument(
        "--pattern",
        type=str,
        default="*",
        help="Glob pattern for input images (default: *)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.in_dir.exists():
        raise SystemExit(f"input dir not found: {args.in_dir}")
    if not args.in_dir.is_dir():
        raise SystemExit(f"input dir is not a directory: {args.in_dir}")

    inputs = sorted(p for p in args.in_dir.glob(args.pattern) if p.is_file())
    if not inputs:
        raise SystemExit(f"no input files found in {args.in_dir} with pattern {args.pattern!r}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for idx, path in enumerate(inputs):
        buf = image_path_to_mono1_buffer(
            path,
            width=int(args.width),
            height=int(args.height),
            invert=bool(args.invert),
        )
        out_path = args.out_dir / f"frame_{idx:03d}.bin"
        out_path.write_bytes(buf)
    print(f"wrote {len(inputs)} frames to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
