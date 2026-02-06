import logging
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.app.oled_mode_manager import OledModeManager, OLED_MODE_SETTINGS, OLED_SETTINGS_ITEMS  # noqa: E402
from dmc_ai_mobility.core.config import RobotConfig  # noqa: E402
from dmc_ai_mobility.drivers.oled import MockOledDriver  # noqa: E402


class TestOledModeManager(unittest.TestCase):
    def _new_manager(self) -> OledModeManager:
        return OledModeManager(
            oled=MockOledDriver(),
            config=RobotConfig(),
            robot_id="test-bot",
            logger=logging.getLogger("test_oled_mode_manager"),
        )

    def test_settings_index_wraps(self) -> None:
        manager = self._new_manager()
        manager.set_mode(OLED_MODE_SETTINGS, use_transition=False)

        self.assertEqual(manager.get_settings_item(), OLED_SETTINGS_ITEMS[0])
        manager.step_settings_index(-1)
        self.assertEqual(manager.get_settings_item(), OLED_SETTINGS_ITEMS[-1])
        manager.step_settings_index(1)
        self.assertEqual(manager.get_settings_item(), OLED_SETTINGS_ITEMS[0])

    def test_settings_confirm_flow(self) -> None:
        manager = self._new_manager()
        manager.set_mode(OLED_MODE_SETTINGS, use_transition=False)

        first = manager.begin_settings_confirm()
        self.assertEqual(first, OLED_SETTINGS_ITEMS[0])
        self.assertTrue(manager.is_settings_confirming())

        manager.cancel_settings_confirm()
        self.assertFalse(manager.is_settings_confirming())

        manager.step_settings_index(1)
        second = manager.begin_settings_confirm()
        self.assertEqual(second, OLED_SETTINGS_ITEMS[1])
        selected = manager.pop_settings_confirm_item()
        self.assertEqual(selected, OLED_SETTINGS_ITEMS[1])
        self.assertFalse(manager.is_settings_confirming())

    def test_leaving_settings_clears_confirm_state(self) -> None:
        manager = self._new_manager()
        manager.set_mode(OLED_MODE_SETTINGS, use_transition=False)
        manager.begin_settings_confirm()
        self.assertTrue(manager.is_settings_confirming())

        manager.set_mode("drive", use_transition=False)
        self.assertFalse(manager.is_settings_confirming())


if __name__ == "__main__":
    unittest.main()
