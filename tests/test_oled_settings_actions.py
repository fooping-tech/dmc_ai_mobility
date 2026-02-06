import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.app.oled_settings_actions import (  # noqa: E402
    get_action_status_duration_ms,
    get_action_status_text,
    get_settings_item_status_duration_ms,
    get_settings_item_status_text,
)


class TestOledSettingsActions(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
