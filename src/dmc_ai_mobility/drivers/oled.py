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


class Ssd1306OledDriver:
    def __init__(self, config: Ssd1306OledConfig) -> None:
        raise RuntimeError(
            "SSD1306 OLED driver is not implemented yet; use MockOledDriver or implement via luma.oled"
        )

    def show_text(self, text: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return
