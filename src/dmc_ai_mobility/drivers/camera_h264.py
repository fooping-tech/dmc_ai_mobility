from __future__ import annotations

import logging
import os
import select
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LibcameraH264Config:
    width: int = 640
    height: int = 480
    fps: float = 30.0
    bitrate: int = 2000000
    chunk_bytes: int = 65536


class LibcameraH264Driver:
    def __init__(self, config: LibcameraH264Config) -> None:
        self._width = int(config.width)
        self._height = int(config.height)
        self._fps = float(config.fps)
        self._bitrate = int(config.bitrate)
        self._chunk_bytes = max(1, int(config.chunk_bytes))
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._start_process()

    def _start_process(self) -> None:
        cmd_name = shutil.which("rpicam-vid") or shutil.which("libcamera-vid")
        if not cmd_name:
            raise RuntimeError(
                "rpicam-vid/libcamera-vid not found; install rpicam-apps (bookworm) or libcamera-apps"
            )
        cmd = [
            cmd_name,
            "--codec",
            "h264",
            "--inline",
            "--width",
            str(self._width),
            "--height",
            str(self._height),
            "--framerate",
            f"{self._fps:.2f}",
            "--timeout",
            "0",
            "--nopreview",
            "-o",
            "-",
        ]
        if self._bitrate > 0:
            cmd.extend(["--bitrate", str(self._bitrate)])
        logger.info("starting camera encoder: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        if self._proc.stderr:
            self._stderr_thread = threading.Thread(
                target=self._stderr_loop, name="libcamera-vid-stderr", daemon=True
            )
            self._stderr_thread.start()

    def _stderr_loop(self) -> None:
        assert self._proc and self._proc.stderr
        while True:
            line = self._proc.stderr.readline()
            if not line:
                break
            logger.info("libcamera-vid: %s", line.decode("utf-8", errors="replace").rstrip())

    def read_chunk(self, *, timeout_s: float = 0.5) -> Optional[bytes]:
        if self._proc is None or self._proc.stdout is None:
            return None
        if self._proc.poll() is not None:
            return None
        rlist, _, _ = select.select([self._proc.stdout], [], [], timeout_s)
        if not rlist:
            return b""
        data = os.read(self._proc.stdout.fileno(), self._chunk_bytes)
        if not data:
            return None
        return data

    def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None


class MockH264Driver:
    def __init__(self, *, fps: float = 10.0, chunk_bytes: int = 256) -> None:
        self._interval_s = 1.0 / fps if fps > 0 else 0.1
        self._chunk = (b"\x00\x00\x00\x01" + b"MOCKH264")[: max(8, chunk_bytes)]

    def read_chunk(self, *, timeout_s: float = 0.5) -> Optional[bytes]:
        time.sleep(self._interval_s)
        return self._chunk

    def close(self) -> None:
        return
