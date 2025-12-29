from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class OledDriver(Protocol):
    def show_text(self, text: str) -> None: ...
    def close(self) -> None: ...


class MockOledDriver:
    def __init__(self) -> None:
        self._last = ""

    def show_text(self, text: str) -> None:
        if text != self._last:
            logger.info("mock oled text=%r", text)
            self._last = text

    def close(self) -> None:
        return


@dataclass(frozen=True)
class Ssd1306OledConfig:
    i2c_port: int = 1
    i2c_address: int = 0x3C
    width: int = 128
    height: int = 32
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_size: int = 14


class Ssd1306OledDriver:
    def __init__(self, config: Ssd1306OledConfig) -> None:
        try:
            import board  # type: ignore
            import busio  # type: ignore
            import adafruit_ssd1306  # type: ignore
            from PIL import Image, ImageDraw, ImageFont  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "OLED dependencies are missing (pip install adafruit-blinka adafruit-circuitpython-ssd1306 pillow)"
            ) from e

        self._Image = Image
        self._ImageDraw = ImageDraw
        self._ImageFont = ImageFont

        i2c = busio.I2C(board.SCL, board.SDA)
        self._oled = adafruit_ssd1306.SSD1306_I2C(
            config.width, config.height, i2c, addr=int(config.i2c_address)
        )
        self._oled.fill(0)
        self._oled.show()

        self._image = Image.new("1", (self._oled.width, self._oled.height))
        self._draw = ImageDraw.Draw(self._image)
        try:
            self._font = ImageFont.truetype(config.font_path, config.font_size)
        except Exception:
            self._font = ImageFont.load_default()
        self._last = ""

    def show_text(self, text: str) -> None:
        if text == self._last:
            return
        self._last = text

        self._draw.rectangle((0, 0, self._oled.width, self._oled.height), outline=0, fill=0)
        lines = (text or "").splitlines() or [""]
        line_height = self._font.size + 2 if hasattr(self._font, "size") else 16
        y = 0
        for line in lines:
            if y >= self._oled.height:
                break
            self._draw.text((0, y), line, font=self._font, fill=255)
            y += line_height

        self._oled.image(self._image)
        self._oled.show()
        logger.info("oled updated text=%r", text)

    def close(self) -> None:
        try:
            self._oled.fill(0)
            self._oled.show()
        except Exception:
            pass
