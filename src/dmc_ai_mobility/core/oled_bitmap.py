from __future__ import annotations

from pathlib import Path
from typing import Optional


def mono1_buf_len(width: int, height: int) -> int:
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be > 0")
    if height % 8 != 0:
        raise ValueError("height must be a multiple of 8 for SSD1306 mono1 buffer")
    return (width * height) // 8


def load_mono1_buffer(path: Path, *, width: int, height: int) -> bytes:
    expected = mono1_buf_len(width, height)
    data = path.read_bytes()
    if len(data) != expected:
        raise ValueError(f"invalid mono1 buffer length: got={len(data)} expected={expected} ({width}x{height})")
    return data


def _require_pillow() -> tuple[object, object]:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pillow is required for image->mono1 conversion (pip install pillow)") from e
    return Image, ImageOps


def image_path_to_mono1_buffer(
    path: Path,
    *,
    width: int,
    height: int,
    invert: bool = False,
) -> bytes:
    """
    Convert an image file (png/jpg/pbm/...) into SSD1306 mono1 buffer bytes.

    The buffer layout follows SSD1306 "page" order:
      - index = x + page*width where page = y//8
      - bit = y%8 (LSB is the top pixel within the 8-pixel page)
    """
    Image, ImageOps = _require_pillow()
    img = Image.open(path)
    img = img.convert("L")
    if invert:
        img = ImageOps.invert(img)
    img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
    img = img.convert("1")  # 1-bit
    return pil_image_to_mono1_buffer(img, width=width, height=height)


def pil_image_to_mono1_buffer(img: object, *, width: int, height: int) -> bytes:
    Image, _ = _require_pillow()
    if not isinstance(img, Image.Image):  # pragma: no cover
        raise TypeError("img must be a PIL.Image.Image")

    if img.size != (width, height):
        img = img.resize((int(width), int(height)), Image.Resampling.NEAREST)
    if img.mode != "1":
        img = img.convert("1")

    expected = mono1_buf_len(width, height)
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


def mono1_buffer_to_pil_image(buf: bytes, *, width: int, height: int) -> object:
    Image, _ = _require_pillow()
    expected = mono1_buf_len(width, height)
    if len(buf) != expected:
        raise ValueError(f"invalid mono1 buffer length: got={len(buf)} expected={expected} ({width}x{height})")
    img = Image.new("1", (int(width), int(height)))
    px = img.load()
    for y in range(height):
        page = y // 8
        bit = y % 8
        base = page * width
        for x in range(width):
            px[x, y] = 255 if (buf[base + x] & (1 << bit)) else 0
    return img


def load_oled_asset_mono1(
    path: Optional[str],
    *,
    width: int,
    height: int,
    invert: bool = False,
) -> Optional[bytes]:
    if not path:
        return None
    p = Path(path)
    if p.suffix.lower() == ".bin":
        return load_mono1_buffer(p, width=width, height=height)
    return image_path_to_mono1_buffer(p, width=width, height=height, invert=invert)

