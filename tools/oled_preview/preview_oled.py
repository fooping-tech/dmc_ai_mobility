#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dmc_ai_mobility.core.oled_bitmap import (  # noqa: E402
    image_path_to_mono1_buffer,
    mono1_buffer_to_pil_image,
    mono1_buf_len,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview SSD1306 mono1 buffers on a desktop.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--bin", type=Path, help="Path to a mono1 .bin buffer")
    src.add_argument("--image", type=Path, help="Path to an input image (png/jpg/...)")
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=32)
    parser.add_argument("--invert", action="store_true", help="Invert input image before conversion (image only)")
    parser.add_argument("--scale", type=int, default=4, help="Scale factor for preview image")
    parser.add_argument("--out", type=Path, default=None, help="Output image path (png)")
    parser.add_argument("--show", action="store_true", help="Open preview with default image viewer")
    return parser.parse_args(argv)


def _load_buffer(args: argparse.Namespace) -> bytes:
    if args.bin:
        data = args.bin.read_bytes()
    else:
        data = image_path_to_mono1_buffer(
            args.image,
            width=int(args.width),
            height=int(args.height),
            invert=bool(args.invert),
        )
    expected = mono1_buf_len(int(args.width), int(args.height))
    if len(data) != expected:
        raise SystemExit(
            f"invalid mono1 buffer length: got={len(data)} expected={expected} ({args.width}x{args.height})"
        )
    return data


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.scale <= 0:
        raise SystemExit("--scale must be > 0")

    buf = _load_buffer(args)
    img = mono1_buffer_to_pil_image(buf, width=int(args.width), height=int(args.height))
    if args.scale != 1:
        try:
            from PIL import Image  # type: ignore

            resample = Image.Resampling.NEAREST
        except Exception:
            resample = 0
        img = img.resize(
            (int(args.width) * int(args.scale), int(args.height) * int(args.scale)),
            resample=resample,
        )

    out = args.out
    if out is None and not args.show:
        out = Path("preview.png")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        print(f"wrote {out}")

    if args.show:
        img.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
