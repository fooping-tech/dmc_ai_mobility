import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.app.oled_settings_actions import get_action_status_text, get_settings_item_status_text  # noqa: E402


class TestOledSettingsActions(unittest.TestCase):
    def test_action_status_text_for_power_actions(self) -> None:
        self.assertEqual(get_action_status_text("shutdown"), "SHUTDOWN\nnow...")
        self.assertEqual(get_action_status_text("reboot"), "REBOOT\nnow...")

    def test_settings_item_status_text_for_power_items(self) -> None:
        self.assertEqual(get_settings_item_status_text("SHUTDOWN"), "SHUTDOWN\nnow...")
        self.assertEqual(get_settings_item_status_text("REBOOT"), "REBOOT\nnow...")

    def test_settings_item_status_text_for_non_power_item(self) -> None:
        self.assertIsNone(get_settings_item_status_text("WIFI"))


if __name__ == "__main__":
    unittest.main()
