from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from dmc_ai_mobility.core.oled_bitmap import (
    load_oled_asset_mono1,
    mono1_buffer_to_pil_image,
    pil_image_to_mono1_buffer,
)


def _load_pillow() -> Optional[tuple[object, object, object]]:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None
    return Image, ImageDraw, ImageFont


def _load_font(image_font: object, font_path: Optional[str], font_size: int) -> object:
    try:
        if font_path:
            return image_font.truetype(font_path, font_size)
    except Exception:
        pass
    return image_font.load_default()


@dataclass(frozen=True)
class OledFrameSequence:
    frames: list[bytes]
    fps: float = 10.0
    loop: bool = True

    def frame_at(self, now_ms: int, start_ms: int) -> tuple[Optional[bytes], bool]:
        if not self.frames:
            return None, True
        fps = max(float(self.fps), 0.1)
        frame_ms = 1000.0 / fps
        index = int(max(0, now_ms - start_ms) / frame_ms)
        if self.loop:
            return self.frames[index % len(self.frames)], False
        if index >= len(self.frames):
            return self.frames[-1], True
        return self.frames[index], False


def load_oled_frames_dir(path: Optional[str], *, width: int, height: int) -> list[bytes]:
    if not path:
        return []
    base = Path(path)
    if not base.exists():
        raise FileNotFoundError(f"frames dir not found: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"frames dir is not a directory: {base}")
    frames: list[bytes] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_file():
            continue
        frame = load_oled_asset_mono1(str(entry), width=width, height=height)
        if frame is not None:
            frames.append(frame)
    if not frames:
        raise ValueError(f"no frames found in {base}")
    return frames


def render_text_overlay(
    base_buf: Optional[bytes],
    *,
    width: int,
    height: int,
    lines: Sequence[str],
    font_path: Optional[str] = None,
    font_size: int = 10,
    line_spacing: int = 1,
    offset_x: int = 0,
    offset_y: int = 0,
) -> Optional[bytes]:
    pillow = _load_pillow()
    if pillow is None:
        return None
    Image, ImageDraw, ImageFont = pillow
    if base_buf:
        img = mono1_buffer_to_pil_image(base_buf, width=width, height=height)
    else:
        img = Image.new("1", (int(width), int(height)))
    draw = ImageDraw.Draw(img)
    font = _load_font(ImageFont, font_path, font_size)
    line_height = int(getattr(font, "size", font_size)) + int(line_spacing)
    y = int(offset_y)
    for line in lines:
        if y >= height:
            break
        draw.text((int(offset_x), y), line, font=font, fill=255)
        y += line_height
    return pil_image_to_mono1_buffer(img, width=width, height=height)


def render_menu_overlay(
    lines: Sequence[str],
    *,
    selected_index: int,
    width: int,
    height: int,
    font_path: Optional[str] = None,
    font_size: int = 10,
    line_spacing: int = 1,
    pad_x: int = 1,
    pad_y: int = 0,
) -> Optional[bytes]:
    pillow = _load_pillow()
    if pillow is None:
        return None
    Image, ImageDraw, ImageFont = pillow
    img = Image.new("1", (int(width), int(height)))
    draw = ImageDraw.Draw(img)
    font = _load_font(ImageFont, font_path, font_size)
    line_height = int(getattr(font, "size", font_size)) + int(line_spacing)
    y = int(pad_y)
    for idx, line in enumerate(lines):
        if y >= height:
            break
        if idx == selected_index:
            draw.rectangle((0, y, int(width) - 1, y + line_height - 1), fill=255)
            draw.text((int(pad_x), y), line, font=font, fill=0)
        else:
            draw.text((int(pad_x), y), line, font=font, fill=255)
        y += line_height
    return pil_image_to_mono1_buffer(img, width=width, height=height)
