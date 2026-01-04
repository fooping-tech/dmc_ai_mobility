from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from dmc_ai_mobility.core.config import RobotConfig
from dmc_ai_mobility.core.oled_bitmap import load_oled_asset_mono1
from dmc_ai_mobility.core.oled_ui import (
    OledFrameSequence,
    load_oled_frames_dir,
    render_menu_overlay,
    render_text_overlay,
)
from dmc_ai_mobility.core.timing import monotonic_ms
from dmc_ai_mobility.core.types import MotorCmd
from dmc_ai_mobility.drivers.oled import OledDriver

OLED_MODE_LEGACY = "legacy"
OLED_MODE_WELCOME = "welcome"
OLED_MODE_DRIVE = "drive"
OLED_MODE_SETTINGS = "settings"

OLED_SETTINGS_ITEMS = (
    "CALIB",
    "WIFI",
    "GIT PULL",
    "BRANCH",
    "SHUTDOWN",
    "REBOOT",
)

ModeRenderer = Callable[[int, Optional[MotorCmd], Optional[int], int], None]


@dataclass
class _ModeSwitchState:
    active: bool = False
    start_ms: int = 0
    target: Optional[str] = None


class OledModeManager:
    def __init__(
        self,
        *,
        oled: OledDriver,
        config: RobotConfig,
        robot_id: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._oled = oled
        self._config = config
        self._robot_id = robot_id
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()

        self._oled_width = int(config.oled.width)
        self._oled_height = int(config.oled.height)

        self._boot_mono1: Optional[bytes] = None
        self._motor_mono1: Optional[bytes] = None
        self._welcome_seq = OledFrameSequence([], fps=float(config.oled.welcome_fps), loop=False)
        self._mode_switch_seq = OledFrameSequence([], fps=float(config.oled.mode_switch_fps), loop=False)
        self._eyes_seq = OledFrameSequence([], fps=float(config.oled.eyes_fps), loop=True)
        self._load_assets()

        self._handlers: dict[str, ModeRenderer] = {}
        self._mode_order: list[str] = []
        self._register_defaults()

        default_mode = str(getattr(config.oled, "default_mode", OLED_MODE_LEGACY) or OLED_MODE_LEGACY).lower()
        if default_mode not in self._handlers:
            self._logger.warning("invalid oled.default_mode=%s; using legacy", default_mode)
            default_mode = OLED_MODE_LEGACY
        self._default_mode = default_mode
        self._mode = default_mode
        self._settings_index = 0
        self._mode_switch = _ModeSwitchState()
        self._welcome_start_ms = 0
        self._welcome_next_mode = self._default_mode
        self._eyes_start_ms = monotonic_ms()

        if self._mode == OLED_MODE_WELCOME:
            self._welcome_start_ms = monotonic_ms()
            self._welcome_next_mode = self._default_mode
        if self._welcome_seq.frames and bool(config.oled.welcome_on_boot):
            self._welcome_start_ms = monotonic_ms()
            self._welcome_next_mode = self._default_mode
            self._mode = OLED_MODE_WELCOME

    def register_mode(self, mode: str, renderer: ModeRenderer) -> None:
        key = str(mode)
        self._handlers[key] = renderer
        if key not in self._mode_order:
            self._mode_order.append(key)

    def register_template_mode(self, mode: str = "custom") -> None:
        label = str(mode).strip() or "custom"

        def render_template(
            now_ms: int,
            motor_cmd: Optional[MotorCmd],
            motor_cmd_ms: Optional[int],
            motor_deadman_ms: int,
        ) -> None:
            del now_ms, motor_cmd, motor_cmd_ms, motor_deadman_ms
            try:
                self._oled.show_text(f"{label.upper()}\nMODE")
            except Exception as e:
                self._logger.warning("oled %s render failed: %s", label, e)

        self.register_mode(label, render_template)

    def has_mode(self, mode: str) -> bool:
        return str(mode) in self._handlers

    def get_mode(self) -> str:
        with self._lock:
            return self._mode

    def list_modes(self) -> list[str]:
        return list(self._mode_order)

    def set_mode_order(self, order: list[str]) -> None:
        cleaned = [str(m) for m in order if self.has_mode(m)]
        if not cleaned:
            return
        self._mode_order = cleaned

    def cycle_mode(
        self,
        delta: int,
        *,
        now_ms: Optional[int] = None,
        use_transition: bool = True,
    ) -> None:
        if not self._mode_order:
            return
        with self._lock:
            current = self._mode
        try:
            idx = self._mode_order.index(current)
        except ValueError:
            idx = 0
        delta_i = 1 if int(delta) >= 0 else -1
        next_idx = (idx + delta_i) % len(self._mode_order)
        self.set_mode(self._mode_order[next_idx], now_ms=now_ms, use_transition=use_transition)

    def step_settings_index(self, delta: int) -> None:
        if not OLED_SETTINGS_ITEMS:
            return
        with self._lock:
            idx = self._settings_index + int(delta)
            self._settings_index = max(0, min(idx, len(OLED_SETTINGS_ITEMS) - 1))

    def get_settings_item(self) -> Optional[str]:
        if not OLED_SETTINGS_ITEMS:
            return None
        with self._lock:
            idx = max(0, min(self._settings_index, len(OLED_SETTINGS_ITEMS) - 1))
            return OLED_SETTINGS_ITEMS[idx]

    def set_mode(
        self,
        mode: str,
        *,
        settings_index: Optional[int] = None,
        now_ms: Optional[int] = None,
        use_transition: bool = True,
    ) -> None:
        mode = str(mode or "").lower()
        if mode not in self._handlers:
            self._logger.warning("invalid oled mode: %s", mode)
            return
        now = monotonic_ms() if now_ms is None else int(now_ms)
        with self._lock:
            if settings_index is not None and OLED_SETTINGS_ITEMS:
                self._settings_index = max(0, min(int(settings_index), len(OLED_SETTINGS_ITEMS) - 1))
            if mode == OLED_MODE_WELCOME:
                self._welcome_start_ms = now
                self._welcome_next_mode = self._default_mode
            if (
                use_transition
                and self._mode_switch_seq.frames
                and (mode != self._mode or self._mode_switch.active)
            ):
                self._mode_switch.active = True
                self._mode_switch.start_ms = now
                self._mode_switch.target = mode
                return
            self._mode = mode

    def render(
        self,
        now_ms: int,
        motor_cmd: Optional[MotorCmd],
        motor_cmd_ms: Optional[int],
        motor_deadman_ms: int,
    ) -> None:
        with self._lock:
            mode = self._mode
            mode_switch_active = self._mode_switch.active
            mode_switch_start_ms = self._mode_switch.start_ms
            mode_switch_target = self._mode_switch.target

        if mode_switch_active and self._mode_switch_seq.frames:
            frame, done = self._mode_switch_seq.frame_at(now_ms, mode_switch_start_ms)
            try:
                if frame is not None:
                    overlay = None
                    if mode_switch_target:
                        overlay = render_text_overlay(
                            frame,
                            width=self._oled_width,
                            height=self._oled_height,
                            lines=("MODE", mode_switch_target.upper()),
                            font_size=10,
                            line_spacing=1,
                        )
                    self._oled.show_mono1(overlay if overlay is not None else frame)
                else:
                    self._oled.show_text("MODE")
            except Exception as e:
                self._logger.warning("oled mode switch render failed: %s", e)
            if done:
                with self._lock:
                    if self._mode_switch.active and self._mode_switch.start_ms == mode_switch_start_ms:
                        self._mode_switch.active = False
                        if mode_switch_target:
                            self._mode = mode_switch_target
                            if mode_switch_target == OLED_MODE_WELCOME:
                                self._welcome_start_ms = now_ms
                                self._welcome_next_mode = self._default_mode
                        self._mode_switch.target = None
            return

        handler = self._handlers.get(mode)
        if handler is None:
            self._logger.warning("oled mode handler missing: %s", mode)
            handler = self._render_legacy
        handler(now_ms, motor_cmd, motor_cmd_ms, motor_deadman_ms)
        return

    def _register_defaults(self) -> None:
        self.register_mode(OLED_MODE_LEGACY, self._render_legacy)
        self.register_mode(OLED_MODE_WELCOME, self._render_welcome)
        self.register_mode(OLED_MODE_DRIVE, self._render_drive)
        self.register_mode(OLED_MODE_SETTINGS, self._render_settings)

    def _render_welcome(
        self,
        now_ms: int,
        motor_cmd: Optional[MotorCmd],
        motor_cmd_ms: Optional[int],
        motor_deadman_ms: int,
    ) -> None:
        del motor_cmd, motor_cmd_ms, motor_deadman_ms
        with self._lock:
            welcome_start_ms = self._welcome_start_ms
            welcome_next_mode = self._welcome_next_mode
        if self._welcome_seq.frames:
            frame, done = self._welcome_seq.frame_at(now_ms, welcome_start_ms)
            try:
                if frame is not None:
                    self._oled.show_mono1(frame)
                else:
                    self._oled.show_text(f"{self._robot_id}\nWELCOME")
            except Exception as e:
                self._logger.warning("oled welcome render failed: %s", e)
            if done and not self._welcome_seq.loop:
                self.set_mode(welcome_next_mode, now_ms=now_ms, use_transition=True)
            return
        try:
            self._oled.show_text(f"{self._robot_id}\nWELCOME")
        except Exception as e:
            self._logger.warning("oled welcome render failed: %s", e)

    def _render_drive(
        self,
        now_ms: int,
        motor_cmd: Optional[MotorCmd],
        motor_cmd_ms: Optional[int],
        motor_deadman_ms: int,
    ) -> None:
        del motor_cmd_ms, motor_deadman_ms
        cmd = motor_cmd
        v_l = float(cmd.v_l) if cmd else 0.0
        v_r = float(cmd.v_r) if cmd else 0.0
        lines = (f"L:{v_l:+.2f}", f"R:{v_r:+.2f}")
        font_size = 10
        line_spacing = 1
        line_height = font_size + line_spacing
        offset_y = max(0, self._oled_height - line_height * len(lines))
        try:
            frame = None
            if self._eyes_seq.frames:
                frame, _ = self._eyes_seq.frame_at(now_ms, self._eyes_start_ms)
            overlay = render_text_overlay(
                frame,
                width=self._oled_width,
                height=self._oled_height,
                lines=lines,
                font_size=font_size,
                line_spacing=line_spacing,
                offset_y=offset_y,
            )
            if overlay is not None:
                self._oled.show_mono1(overlay)
            else:
                self._oled.show_text("\n".join(lines))
        except Exception as e:
            self._logger.warning("oled drive render failed: %s", e)

    def _render_settings(
        self,
        now_ms: int,
        motor_cmd: Optional[MotorCmd],
        motor_cmd_ms: Optional[int],
        motor_deadman_ms: int,
    ) -> None:
        del motor_cmd, motor_cmd_ms, motor_deadman_ms
        with self._lock:
            settings_index = self._settings_index
        page_size = 2
        safe_index = max(0, min(int(settings_index), len(OLED_SETTINGS_ITEMS) - 1))
        page_start = (safe_index // page_size) * page_size
        lines = OLED_SETTINGS_ITEMS[page_start : page_start + page_size]
        local_index = safe_index - page_start
        try:
            overlay = render_menu_overlay(
                lines,
                selected_index=local_index,
                width=self._oled_width,
                height=self._oled_height,
                font_size=10,
                line_spacing=1,
            )
            if overlay is not None:
                self._oled.show_mono1(overlay)
            else:
                text_lines = []
                for idx, line in enumerate(lines):
                    prefix = ">" if idx == local_index else " "
                    text_lines.append(f"{prefix}{line}")
                self._oled.show_text("\n".join(text_lines))
        except Exception as e:
            self._logger.warning("oled settings render failed: %s", e)

    def _render_legacy(
        self,
        now_ms: int,
        motor_cmd: Optional[MotorCmd],
        motor_cmd_ms: Optional[int],
        motor_deadman_ms: int,
    ) -> None:
        cmd = motor_cmd
        cmd_ms = motor_cmd_ms
        deadman = int(motor_deadman_ms)
        moving = bool(cmd and (abs(cmd.v_l) > 1e-3 or abs(cmd.v_r) > 1e-3))
        fresh = bool(cmd_ms is not None and (now_ms - int(cmd_ms)) <= deadman)
        try:
            if fresh and moving:
                if self._motor_mono1 is not None:
                    self._oled.show_mono1(self._motor_mono1)
                else:
                    self._oled.show_text(f"{self._robot_id}\nMOTOR")
            else:
                if self._boot_mono1 is not None:
                    self._oled.show_mono1(self._boot_mono1)
                else:
                    self._oled.show_text(f"{self._robot_id}\nREADY")
        except Exception as e:
            self._logger.warning("oled base render failed: %s", e)

    def _load_assets(self) -> None:
        try:
            self._boot_mono1 = load_oled_asset_mono1(
                self._config.oled.boot_image,
                width=self._oled_width,
                height=self._oled_height,
            )
        except Exception as e:
            self._logger.warning("failed to load oled.boot_image (%s): %s", self._config.oled.boot_image, e)
        try:
            self._motor_mono1 = load_oled_asset_mono1(
                self._config.oled.motor_image,
                width=self._oled_width,
                height=self._oled_height,
            )
        except Exception as e:
            self._logger.warning("failed to load oled.motor_image (%s): %s", self._config.oled.motor_image, e)

        if self._config.oled.welcome_frames_dir:
            try:
                frames = load_oled_frames_dir(
                    self._config.oled.welcome_frames_dir,
                    width=self._oled_width,
                    height=self._oled_height,
                )
                self._welcome_seq = OledFrameSequence(
                    frames,
                    fps=float(self._config.oled.welcome_fps),
                    loop=bool(self._config.oled.welcome_loop),
                )
            except Exception as e:
                self._logger.warning(
                    "failed to load oled.welcome_frames_dir (%s): %s",
                    self._config.oled.welcome_frames_dir,
                    e,
                )
        if self._config.oled.mode_switch_frames_dir:
            try:
                frames = load_oled_frames_dir(
                    self._config.oled.mode_switch_frames_dir,
                    width=self._oled_width,
                    height=self._oled_height,
                )
                self._mode_switch_seq = OledFrameSequence(
                    frames,
                    fps=float(self._config.oled.mode_switch_fps),
                    loop=False,
                )
            except Exception as e:
                self._logger.warning(
                    "failed to load oled.mode_switch_frames_dir (%s): %s",
                    self._config.oled.mode_switch_frames_dir,
                    e,
                )
        if self._config.oled.eyes_frames_dir:
            try:
                frames = load_oled_frames_dir(
                    self._config.oled.eyes_frames_dir,
                    width=self._oled_width,
                    height=self._oled_height,
                )
                self._eyes_seq = OledFrameSequence(
                    frames,
                    fps=float(self._config.oled.eyes_fps),
                    loop=True,
                )
            except Exception as e:
                self._logger.warning(
                    "failed to load oled.eyes_frames_dir (%s): %s",
                    self._config.oled.eyes_frames_dir,
                    e,
                )
