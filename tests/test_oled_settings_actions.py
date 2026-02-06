import logging
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.app.oled_settings_actions import (  # noqa: E402
    ACTION_BRANCH,
    ACTION_GIT_PULL,
    ActionEvent,
    OledSettingsActionRunner,
    get_action_status_duration_ms,
    get_action_status_text,
    get_settings_item_status_duration_ms,
    get_settings_item_status_text,
)
from dmc_ai_mobility.core.config import OledSettingsConfig, RobotConfig  # noqa: E402


class TestOledSettingsActions(unittest.TestCase):
    def _wait_events(self, events: list[ActionEvent], n: int, timeout_s: float = 1.0) -> None:
        deadline = time.time() + timeout_s
        while len(events) < n and time.time() < deadline:
            time.sleep(0.01)

    def test_action_status_text_for_supported_actions(self) -> None:
        self.assertEqual(get_action_status_text("git_pull"), "GIT PULL\nrunning...")
        self.assertEqual(get_action_status_text("shutdown"), "SHUTDOWN\nnow...")
        self.assertEqual(get_action_status_text("reboot"), "REBOOT\nnow...")

    def test_settings_item_status_text_for_supported_items(self) -> None:
        self.assertEqual(get_settings_item_status_text("GIT PULL"), "GIT PULL\nrunning...")
        self.assertEqual(get_settings_item_status_text("SHUTDOWN"), "SHUTDOWN\nnow...")
        self.assertEqual(get_settings_item_status_text("REBOOT"), "REBOOT\nnow...")

    def test_settings_item_status_text_for_non_power_item(self) -> None:
        self.assertIsNone(get_settings_item_status_text("WIFI"))

    def test_action_status_duration_ms_for_supported_actions(self) -> None:
        self.assertEqual(get_action_status_duration_ms("git_pull"), 8000)
        self.assertEqual(get_action_status_duration_ms("shutdown"), 3000)
        self.assertEqual(get_action_status_duration_ms("reboot"), 3000)

    def test_settings_item_status_duration_ms_for_supported_items(self) -> None:
        self.assertEqual(get_settings_item_status_duration_ms("GIT PULL"), 8000)
        self.assertEqual(get_settings_item_status_duration_ms("SHUTDOWN"), 3000)
        self.assertEqual(get_settings_item_status_duration_ms("REBOOT"), 3000)

    def test_runner_emits_done_event_in_dry_run(self) -> None:
        events: list[ActionEvent] = []
        cfg = RobotConfig(oled_settings=OledSettingsConfig(cooldown_s=0.0))
        runner = OledSettingsActionRunner(
            config=cfg,
            logger=logging.getLogger("test_oled_settings_actions"),
            dry_run=True,
            on_event=events.append,
        )
        self.assertTrue(runner.trigger(ACTION_GIT_PULL))
        self._wait_events(events, 1)
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[-1].action, ACTION_GIT_PULL)
        self.assertEqual(events[-1].status, "done")
        self.assertEqual(events[-1].reason, "dry_run")

    def test_runner_emits_failed_event_when_not_configured(self) -> None:
        events: list[ActionEvent] = []
        cfg = RobotConfig(oled_settings=OledSettingsConfig(cooldown_s=0.0))
        runner = OledSettingsActionRunner(
            config=cfg,
            logger=logging.getLogger("test_oled_settings_actions"),
            dry_run=False,
            on_event=events.append,
        )
        self.assertTrue(runner.trigger(ACTION_BRANCH))
        self._wait_events(events, 1)
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[-1].action, ACTION_BRANCH)
        self.assertEqual(events[-1].status, "failed")
        self.assertEqual(events[-1].reason, "not_configured")

    def test_runner_emits_rejected_event_when_disabled(self) -> None:
        events: list[ActionEvent] = []
        cfg = RobotConfig(oled_settings=OledSettingsConfig(enabled=False, cooldown_s=0.0))
        runner = OledSettingsActionRunner(
            config=cfg,
            logger=logging.getLogger("test_oled_settings_actions"),
            dry_run=False,
            on_event=events.append,
        )
        self.assertFalse(runner.trigger(ACTION_GIT_PULL))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, ACTION_GIT_PULL)
        self.assertEqual(events[0].status, "rejected")
        self.assertEqual(events[0].reason, "disabled")


if __name__ == "__main__":
    unittest.main()
