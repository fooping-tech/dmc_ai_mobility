from __future__ import annotations

import logging
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

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

ACTION_TO_STATUS_TEXT = {
    ACTION_GIT_PULL: "GIT PULL\nrunning...",
    ACTION_SHUTDOWN: "SHUTDOWN\nnow...",
    ACTION_REBOOT: "REBOOT\nnow...",
}

ACTION_TO_STATUS_DURATION_MS = {
    ACTION_GIT_PULL: 8000,
    ACTION_SHUTDOWN: 3000,
    ACTION_REBOOT: 3000,
}

GIT_PULL_REASON_TO_STATUS = {
    "dirty": "DIRTY",
    "non_fast_forward": "NON-FF",
    "detached_head": "DETACHED",
    "remote_missing": "NO-REMOTE",
    "no_sudo": "NO-SUDO",
    "systemctl_missing": "NO-SYSTEMCTL",
    "not_git_repo": "NO-REPO",
    "git_missing": "NO-GIT",
    "not_configured": "NO-CONFIG",
    "busy": "BUSY",
    "cooldown": "COOLDOWN",
    "disabled": "DISABLED",
    "exception": "ERROR",
}


@dataclass(frozen=True)
class ResolvedCommand:
    argv: list[str]
    env: dict[str, str]


@dataclass(frozen=True)
class ActionEvent:
    action: str
    status: str
    returncode: Optional[int] = None
    reason: Optional[str] = None


def get_action_status_text(action: str) -> Optional[str]:
    return ACTION_TO_STATUS_TEXT.get(str(action).strip().lower())


def get_settings_item_status_text(item: str) -> Optional[str]:
    action = SETTINGS_LABEL_TO_ACTION.get(str(item).strip().upper())
    if not action:
        return None
    return get_action_status_text(action)


def get_action_status_duration_ms(action: str) -> Optional[int]:
    return ACTION_TO_STATUS_DURATION_MS.get(str(action).strip().lower())


def get_settings_item_status_duration_ms(item: str) -> Optional[int]:
    action = SETTINGS_LABEL_TO_ACTION.get(str(item).strip().upper())
    if not action:
        return None
    return get_action_status_duration_ms(action)


def get_action_failure_status_text(
    action: str,
    *,
    reason: Optional[str] = None,
    returncode: Optional[int] = None,
) -> Optional[str]:
    if str(action).strip().lower() != ACTION_GIT_PULL:
        return None
    if reason:
        label = GIT_PULL_REASON_TO_STATUS.get(str(reason).strip().lower())
        if label:
            return f"GIT PULL\n{label}"
    if returncode is not None:
        return f"GIT PULL\nFAILED({int(returncode)})"
    return "GIT PULL\nFAILED"


def infer_action_failure_reason(
    action: str,
    *,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> Optional[str]:
    act = str(action).strip().lower()
    if int(returncode) == 0:
        return None
    if act not in {ACTION_GIT_PULL, ACTION_BRANCH}:
        return "exit_code"
    out = f"{stdout}\n{stderr}".lower()
    if "working tree is dirty" in out:
        return "dirty"
    if "non-fast-forward update detected" in out:
        return "non_fast_forward"
    if "detached head" in out:
        return "detached_head"
    if "remote branch not found" in out:
        return "remote_missing"
    if "run as root or set sudo=sudo" in out:
        return "no_sudo"
    if "systemctl not found" in out:
        return "systemctl_missing"
    if "not a git repository" in out:
        return "not_git_repo"
    if "git not found" in out:
        return "git_missing"
    return "exit_code"


class OledSettingsActionRunner:
    def __init__(
        self,
        *,
        config: RobotConfig,
        logger: logging.Logger,
        dry_run: bool = False,
        on_event: Optional[Callable[[ActionEvent], None]] = None,
    ) -> None:
        self._config = config
        self._settings = config.oled_settings
        self._logger = logger
        self._dry_run = dry_run
        self._on_event = on_event
        self._lock = threading.Lock()
        self._in_progress = False
        self._last_action_ms = 0
        self._repo_root = Path(__file__).resolve().parents[3]

    def trigger_item(self, item: str) -> bool:
        action = SETTINGS_LABEL_TO_ACTION.get(str(item).strip().upper())
        if not action:
            self._logger.warning("unknown settings item: %s", item)
            self._emit(ActionEvent(action="unknown", status="rejected", reason="unknown_item"))
            return False
        return self.trigger(action)

    def trigger(self, action: str) -> bool:
        if not self._settings.enabled:
            self._logger.info("settings actions disabled; ignoring %s", action)
            self._emit(ActionEvent(action=action, status="rejected", reason="disabled"))
            return False
        now = monotonic_ms()
        cooldown_ms = int(max(float(self._settings.cooldown_s), 0.0) * 1000.0)
        with self._lock:
            if self._in_progress:
                self._logger.info("settings action busy; ignoring %s", action)
                self._emit(ActionEvent(action=action, status="rejected", reason="busy"))
                return False
            if cooldown_ms and now - self._last_action_ms < cooldown_ms:
                self._logger.info("settings action cooldown; ignoring %s", action)
                self._emit(ActionEvent(action=action, status="rejected", reason="cooldown"))
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
                self._emit(ActionEvent(action=action, status="failed", reason="not_configured"))
                return
            if self._dry_run:
                self._logger.info("settings action dry-run: %s -> %s", action, resolved.argv)
                self._emit(ActionEvent(action=action, status="done", reason="dry_run"))
                return
            self._logger.info("settings action start: %s", action)
            self._emit(ActionEvent(action=action, status="started"))
            result = subprocess.run(
                resolved.argv,
                cwd=self._repo_root,
                env=resolved.env,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.stdout:
                for line in result.stdout.splitlines():
                    self._logger.info("settings action output: %s", line)
            if result.stderr:
                log_fn = self._logger.warning if result.returncode != 0 else self._logger.info
                for line in result.stderr.splitlines():
                    log_fn("settings action output: %s", line)
            if result.returncode != 0:
                reason = infer_action_failure_reason(
                    action,
                    returncode=int(result.returncode),
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                )
                self._logger.warning("settings action failed: %s (code=%s)", action, result.returncode)
                self._emit(
                    ActionEvent(
                        action=action,
                        status="failed",
                        returncode=int(result.returncode),
                        reason=reason,
                    )
                )
            else:
                self._logger.info("settings action done: %s", action)
                self._emit(ActionEvent(action=action, status="done", returncode=0))
        except Exception as e:
            self._logger.warning("settings action error: %s (%s)", action, e)
            self._emit(ActionEvent(action=action, status="failed", reason="exception"))
        finally:
            with self._lock:
                self._in_progress = False
                self._last_action_ms = monotonic_ms()

    def _emit(self, event: ActionEvent) -> None:
        cb = self._on_event
        if cb is None:
            return
        try:
            cb(event)
        except Exception as e:
            self._logger.debug("settings action event callback failed: %s", e)

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
