from __future__ import annotations

import logging
from dataclasses import dataclass
import time
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
        self._device = config.device
        self._width = config.width
        self._height = config.height
        self._cap = self._open_capture()
        self._fail_count = 0
        self._last_warn_ms = 0.0
        self._last_reopen_ms = 0.0

    def _open_capture(self):
        # Prefer V4L2 backend when available (common on Raspberry Pi / Linux),
        # but fall back to the default backend if CAP_V4L2 behaves poorly in a given setup.
        cap = None
        last_err: Exception | None = None
        candidates = []
        if hasattr(self._cv2, "CAP_V4L2"):
            candidates.append((self._device, self._cv2.CAP_V4L2))
        candidates.append((self._device,))

        for args in candidates:
            try:
                cap = self._cv2.VideoCapture(*args)
                if cap.isOpened():
                    break
            except Exception as e:  # pragma: no cover
                last_err = e
                cap = None

        if cap is None:
            raise RuntimeError(f"camera open failed (device={self._device})") from last_err
        cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        if not cap.isOpened():
            raise RuntimeError(
                f"camera open failed (device={self._device}). "
                "Check /dev/video*, permissions, and whether libcamerify/libcamera is configured."
            )
        logger.info("camera opened (device=%s, %sx%s)", self._device, self._width, self._height)
        # Warm up auto exposure by discarding a few frames.
        for _ in range(10):
            try:
                cap.read()
                time.sleep(0.05)
            except Exception:
                break
        return cap

    def read_jpeg(self) -> Optional[Tuple[bytes, int, int]]:
        try:
            ok, frame = self._cap.read()
        except Exception:
            ok, frame = False, None
        if not ok:
            self._fail_count += 1
            now_ms = time.monotonic() * 1000.0
            # Throttle warnings to avoid flooding logs when the camera disappears.
            if now_ms - self._last_warn_ms > 5000:
                logger.warning(
                    "camera read failed (device=%s, fails=%d). "
                    "If this persists, try --no-camera and verify the V4L2 device.",
                    self._device,
                    self._fail_count,
                )
                self._last_warn_ms = now_ms

            # Attempt to reopen periodically after repeated failures.
            if self._fail_count >= 30 and (now_ms - self._last_reopen_ms) > 5000:
                self._last_reopen_ms = now_ms
                try:
                    self._cap.release()
                except Exception:
                    pass
                try:
                    self._cap = self._open_capture()
                    self._fail_count = 0
                except Exception as e:
                    logger.debug("camera reopen failed: %s", e)
            return None
        ok, buf = self._cv2.imencode(".jpg", frame)
        if not ok:
            logger.warning("camera jpeg encode failed")
            return None
        return (bytes(buf), int(frame.shape[1]), int(frame.shape[0]))

    def close(self) -> None:
        self._cap.release()
