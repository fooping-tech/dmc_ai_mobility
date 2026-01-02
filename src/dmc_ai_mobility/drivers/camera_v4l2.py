from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
import time
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

_MOCK_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGn/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9k="
)


@dataclass(frozen=True)
class CameraFrame:
    jpeg: bytes
    width: int
    height: int
    capture_wall_ms: int
    capture_mono_ms: int
    capture_start_mono_ms: int
    capture_end_mono_ms: int
    read_ms: int


class CameraDriver(Protocol):
    def read_jpeg(self) -> Optional[CameraFrame]: ...
    def close(self) -> None: ...


class MockCameraDriver:
    def __init__(self, width: int = 640, height: int = 480) -> None:
        self._width = int(width)
        self._height = int(height)

    def read_jpeg(self) -> Optional[CameraFrame]:
        now_wall_ms = int(time.time() * 1000)
        now_mono_ms = int(time.monotonic() * 1000)
        return CameraFrame(
            jpeg=_MOCK_JPEG,
            width=self._width,
            height=self._height,
            capture_wall_ms=now_wall_ms,
            capture_mono_ms=now_mono_ms,
            capture_start_mono_ms=now_mono_ms,
            capture_end_mono_ms=now_mono_ms,
            read_ms=0,
        )

    def close(self) -> None:
        return


@dataclass(frozen=True)
class OpenCVCameraConfig:
    device: int = 0
    width: int = 640
    height: int = 480
    auto_trim: bool = False
    buffer_size: int = 0


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
        self._auto_trim = bool(config.auto_trim)
        self._buffer_size = int(config.buffer_size)
        self._trim_logged = False
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
        if self._buffer_size > 0 and hasattr(self._cv2, "CAP_PROP_BUFFERSIZE"):
            ok = cap.set(self._cv2.CAP_PROP_BUFFERSIZE, self._buffer_size)
            if ok:
                logger.info("camera buffer size set to %s", self._buffer_size)
            else:
                logger.warning("camera buffer size set failed (value=%s)", self._buffer_size)
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

    def read_jpeg(self) -> Optional[CameraFrame]:
        # cap.read() の開始時刻（キャプチャ開始の近似）
        capture_start_mono_ms = int(time.monotonic() * 1000)
        try:
            ok, frame = self._cap.read()
        except Exception:
            ok, frame = False, None
        # cap.read() の終了時刻（キャプチャ終了の近似）
        capture_end_mono_ms = int(time.monotonic() * 1000)
        if not ok or frame is None:
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
        # Successful read: clear transient failure state.
        self._fail_count = 0
        # 以降のレイテンシ計測はキャプチャ終了時刻を基準にする
        capture_mono_ms = capture_end_mono_ms
        capture_wall_ms = int(time.time() * 1000)
        read_ms = max(0, capture_end_mono_ms - capture_start_mono_ms)
        if self._auto_trim:
            orig_h, orig_w = frame.shape[:2]
            target_w = int(self._width)
            target_h = int(self._height)
            trimmed = False
            if target_w > 0 and orig_w > target_w:
                frame = frame[:, :target_w]
                trimmed = True
            if target_h > 0 and orig_h > target_h:
                frame = frame[:target_h, :]
                trimmed = True
            if trimmed and not self._trim_logged:
                new_h, new_w = frame.shape[:2]
                logger.info(
                    "camera frame trimmed to %sx%s (from %sx%s)",
                    new_w,
                    new_h,
                    orig_w,
                    orig_h,
                )
                self._trim_logged = True

        ok, buf = self._cv2.imencode(".jpg", frame)
        if not ok:
            logger.warning("camera jpeg encode failed")
            return None
        return CameraFrame(
            jpeg=bytes(buf),
            width=int(frame.shape[1]),
            height=int(frame.shape[0]),
            capture_wall_ms=capture_wall_ms,
            capture_mono_ms=capture_mono_ms,
            capture_start_mono_ms=capture_start_mono_ms,
            capture_end_mono_ms=capture_end_mono_ms,
            read_ms=read_ms,
        )

    def close(self) -> None:
        self._cap.release()
