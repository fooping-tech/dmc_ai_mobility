import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.zenoh import keys  # noqa: E402


class TestZenohKeys(unittest.TestCase):
    def test_keys_match_design(self) -> None:
        robot_id = "rasp-zero-01"
        self.assertEqual(keys.motor_cmd(robot_id), "dmc_robo/rasp-zero-01/motor/cmd")
        self.assertEqual(keys.imu_state(robot_id), "dmc_robo/rasp-zero-01/imu/state")
        self.assertEqual(keys.oled_cmd(robot_id), "dmc_robo/rasp-zero-01/oled/cmd")
        self.assertEqual(keys.oled_image_mono1(robot_id), "dmc_robo/rasp-zero-01/oled/image/mono1")
        self.assertEqual(keys.oled_mode(robot_id), "dmc_robo/rasp-zero-01/oled/mode")
        self.assertEqual(keys.camera_image_jpeg(robot_id), "dmc_robo/rasp-zero-01/camera/image/jpeg")
        self.assertEqual(keys.camera_meta(robot_id), "dmc_robo/rasp-zero-01/camera/meta")

    def test_invalid_robot_id(self) -> None:
        with self.assertRaises(ValueError):
            keys.motor_cmd("")
        with self.assertRaises(ValueError):
            keys.motor_cmd("bad/id")


if __name__ == "__main__":
    unittest.main()
