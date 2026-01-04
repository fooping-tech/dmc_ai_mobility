from __future__ import annotations

import logging
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dmc_ai_mobility.core.config import OledSettingsConfig, RobotConfig
from dmc_ai_mobility.core.timing import monotonic_ms

ACTION_CALIB = "calib"
ACTION_WIFI = "wifi"
ACTION_GIT_PULL = "git_pull"
ACTION_BRANCH = "branch"
ACTION_SHUTDOWN = "shutdown"
ACTION_REBOOT = "reboot"

SETTINGS_LABEL_TO_ACTION = {
    "CALIB": ACTION_CALIB,
    "WIFI": ACTION_WIFI,
    "GIT PULL": ACTION_GIT_PULL,
    "BRANCH": ACTION_BRANCH,
    "SHUTDOWN": ACTION_SHUTDOWN,
    "REBOOT": ACTION_REBOOT,
}


@dataclass(frozen=True)
class ResolvedCommand:
    argv: list[str]
    env: dict[str, str]


class OledSettingsActionRunner:
    def __init__(
        self,
        *,
        config: RobotConfig,
        logger: logging.Logger,
        dry_run: bool = False,
    ) -> None:
        self._config = config
        self._settings = config.oled_settings
        self._logger = logger
        self._dry_run = dry_run
        self._lock = threading.Lock()
        self._in_progress = False
        self._last_action_ms = 0
        self._repo_root = Path(__file__).resolve().parents[3]

    def trigger_item(self, item: str) -> bool:
        action = SETTINGS_LABEL_TO_ACTION.get(str(item).strip().upper())
        if not action:
            self._logger.warning("unknown settings item: %s", item)
            return False
        return self.trigger(action)

    def trigger(self, action: str) -> bool:
        if not self._settings.enabled:
            self._logger.info("settings actions disabled; ignoring %s", action)
            return False
        now = monotonic_ms()
        cooldown_ms = int(max(float(self._settings.cooldown_s), 0.0) * 1000.0)
        with self._lock:
            if self._in_progress:
                self._logger.info("settings action busy; ignoring %s", action)
                return False
            if cooldown_ms and now - self._last_action_ms < cooldown_ms:
                self._logger.info("settings action cooldown; ignoring %s", action)
                return False
            self._in_progress = True
        thread = threading.Thread(
            target=self._run_action,
            name=f"oled_settings_{action}",
            args=(action,),
            daemon=True,
        )
        thread.start()
        return True

    def _run_action(self, action: str) -> None:
        try:
            resolved = self._resolve_command(action)
            if resolved is None:
                self._logger.warning("settings action not configured: %s", action)
                return
            if self._dry_run:
                self._logger.info("settings action dry-run: %s -> %s", action, resolved.argv)
                return
            self._logger.info("settings action start: %s", action)
            result = subprocess.run(
                resolved.argv,
                cwd=self._repo_root,
                env=resolved.env,
                check=False,
            )
            if result.returncode != 0:
                self._logger.warning("settings action failed: %s (code=%s)", action, result.returncode)
            else:
                self._logger.info("settings action done: %s", action)
        except Exception as e:
            self._logger.warning("settings action error: %s (%s)", action, e)
        finally:
            with self._lock:
                self._in_progress = False
                self._last_action_ms = monotonic_ms()

    def _resolve_command(self, action: str) -> Optional[ResolvedCommand]:
        settings = self._settings
        env = os.environ.copy()

        if action == ACTION_CALIB:
            cmd = settings.calib_cmd or "python3 -m dmc_ai_mobility.calibration.motor"
            env.setdefault("PYTHONPATH", str(self._repo_root / "src"))
            return ResolvedCommand(argv=shlex.split(cmd), env=env)

        if action == ACTION_WIFI:
            cmd = settings.wifi_cmd or str(self._repo_root / "scripts" / "oled_wifi_connect.sh")
            if settings.wifi_ssid:
                env["WIFI_SSID"] = settings.wifi_ssid
            if settings.wifi_psk_env:
                psk = os.environ.get(settings.wifi_psk_env)
                if psk:
                    env["WIFI_PSK"] = psk
            if "WIFI_SSID" not in env:
                self._logger.warning("wifi action requires WIFI_SSID (oled_settings.wifi_ssid)")
                return None
            return ResolvedCommand(argv=shlex.split(cmd), env=env)

        if action == ACTION_GIT_PULL:
            cmd = settings.git_pull_cmd or str(self._repo_root / "scripts" / "pull_and_restart.sh")
            sudo_cmd = settings.sudo_cmd or "sudo -n"
            if os.geteuid() != 0 and sudo_cmd:
                env.setdefault("SUDO", sudo_cmd)
            return ResolvedCommand(argv=shlex.split(cmd), env=env)

        if action == ACTION_BRANCH:
            cmd = settings.branch_cmd or str(self._repo_root / "scripts" / "oled_switch_branch.sh")
            if settings.branch_target:
                env["TARGET_BRANCH"] = settings.branch_target
            sudo_cmd = settings.sudo_cmd or "sudo -n"
            if os.geteuid() != 0 and sudo_cmd:
                env.setdefault("SUDO", sudo_cmd)
            if "TARGET_BRANCH" not in env:
                self._logger.warning("branch action requires TARGET_BRANCH (oled_settings.branch_target)")
                return None
            return ResolvedCommand(argv=shlex.split(cmd), env=env)

        if action == ACTION_SHUTDOWN:
            cmd = settings.shutdown_cmd or "systemctl poweroff"
            return ResolvedCommand(argv=self._with_sudo_if_needed(cmd, settings), env=env)

        if action == ACTION_REBOOT:
            cmd = settings.reboot_cmd or "systemctl reboot"
            return ResolvedCommand(argv=self._with_sudo_if_needed(cmd, settings), env=env)

        return None

    def _with_sudo_if_needed(self, cmd: str, settings: OledSettingsConfig) -> list[str]:
        argv = shlex.split(cmd)
        if os.geteuid() == 0:
            return argv
        sudo_cmd = settings.sudo_cmd or "sudo -n"
        if not sudo_cmd:
            return argv
        return shlex.split(sudo_cmd) + argv
