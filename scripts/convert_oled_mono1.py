#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.core.oled_bitmap import image_path_to_mono1_buffer, mono1_buf_len  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert an image into SSD1306 mono1 buffer (.bin)")
    p.add_argument("--in", dest="inp", type=Path, required=True, help="Input image path (png/jpg/...)")
    p.add_argument("--out", dest="out", type=Path, required=True, help="Output .bin path")
    p.add_argument("--width", type=int, default=128)
    p.add_argument("--height", type=int, default=32)
    p.add_argument("--invert", action="store_true", help="Invert input image before conversion")
    args = p.parse_args(argv)

    buf = image_path_to_mono1_buffer(args.inp, width=int(args.width), height=int(args.height), invert=bool(args.invert))
    expected = mono1_buf_len(int(args.width), int(args.height))
    if len(buf) != expected:
        raise SystemExit(f"unexpected output size: got={len(buf)} expected={expected}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(buf)
    print(f"wrote {args.out} ({len(buf)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

