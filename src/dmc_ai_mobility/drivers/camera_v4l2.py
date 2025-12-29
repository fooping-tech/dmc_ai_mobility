from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


class CameraDriver(Protocol):
    def read_jpeg(self) -> Optional[Tuple[bytes, int, int]]: ...
    def close(self) -> None: ...


class MockCameraDriver:
    def read_jpeg(self) -> Optional[Tuple[bytes, int, int]]:
        return None

    def close(self) -> None:
        return


@dataclass(frozen=True)
class OpenCVCameraConfig:
    device: int = 0
    width: int = 640
    height: int = 480


class OpenCVCameraDriver:
    def __init__(self, config: OpenCVCameraConfig) -> None:
        try:
            import cv2  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("opencv-python (cv2) is required for OpenCVCameraDriver") from e
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(config.device)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        self._width = config.width
        self._height = config.height

    def read_jpeg(self) -> Optional[Tuple[bytes, int, int]]:
        ok, frame = self._cap.read()
        if not ok:
            logger.warning("camera read failed")
            return None
        ok, buf = self._cv2.imencode(".jpg", frame)
        if not ok:
            logger.warning("camera jpeg encode failed")
            return None
        return (bytes(buf), int(frame.shape[1]), int(frame.shape[0]))

    def close(self) -> None:
        self._cap.release()
