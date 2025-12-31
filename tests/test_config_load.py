import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from dmc_ai_mobility.core.config import load_config  # noqa: E402


class TestConfigLoad(unittest.TestCase):
    def test_load_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = load_config(Path(td) / "missing.toml")
            self.assertEqual(cfg.robot_id, "rasp-zero-01")
            self.assertEqual(cfg.motor.deadman_ms, 300)
            self.assertEqual(cfg.motor.deadband_pw, 0)
            self.assertEqual(cfg.imu.publish_hz, 50.0)
            self.assertEqual(cfg.oled.override_s, 2.0)

    def test_load_from_file_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.toml"
            path.write_text(
                '\n'.join(
                    [
                        'robot_id = "bot-a"',
                        "",
                        "[motor]",
                        "deadman_ms = 123",
                        "deadband_pw = 25",
                        "",
                        "[imu]",
                        "publish_hz = 20",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            cfg = load_config(path, overrides={"robot_id": "bot-b"})
            self.assertEqual(cfg.robot_id, "bot-b")
            self.assertEqual(cfg.motor.deadman_ms, 123)
            self.assertEqual(cfg.motor.deadband_pw, 25)
            self.assertEqual(cfg.imu.publish_hz, 20.0)


if __name__ == "__main__":
    unittest.main()
