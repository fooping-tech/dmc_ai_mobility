import json
import time
from pathlib import Path

import pigpio

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# GPIO
GPIO_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"
DEFAULT_GPIO = {"pin_l": 19, "pin_r": 12}


def load_gpio(path):
    if tomllib is None:
        print("tomllib not available, using default GPIO config.")
        return DEFAULT_GPIO.copy()
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        gpio = data.get("gpio", {})
        return {
            "pin_l": int(gpio.get("pin_l", DEFAULT_GPIO["pin_l"])),
            "pin_r": int(gpio.get("pin_r", DEFAULT_GPIO["pin_r"])),
        }
    except FileNotFoundError:
        print(f"Config not found: {path}, using defaults.")
    except Exception as e:
        print(f"Failed to load GPIO config: {e}, using defaults.")
    return DEFAULT_GPIO.copy()


gpio = load_gpio(GPIO_CONFIG_PATH)
PIN_L = gpio["pin_l"]
PIN_R = gpio["pin_r"]

MOTOR_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "motor_config.json"
BASE_SPEED = 40
RUN_SECONDS = 3


def load_trim(path):
    try:
        with path.open() as f:
            data = json.load(f)
        return float(data.get("trim", 0.0))
    except FileNotFoundError:
        print(f"Config not found: {path}, using trim=0.0")
    except (ValueError, TypeError, json.JSONDecodeError):
        print(f"Invalid config: {path}, using trim=0.0")
    return 0.0


def drive(pi, speed, trim):
    l_factor = 1.0
    r_factor = 1.0

    if trim > 0:
        r_factor = 1.0 + trim
    else:
        l_factor = 1.0 - trim

    pw_l = 1500 + (speed * l_factor * 5)
    pw_r = 1500 - (speed * r_factor * 5)

    pi.set_servo_pulsewidth(PIN_L, pw_l)
    pi.set_servo_pulsewidth(PIN_R, pw_r)


def main():
    trim = load_trim(MOTOR_CONFIG_PATH)
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpio not connected.")
        return

    try:
        print(f"Driving forward with trim={trim:.3f}")
        drive(pi, BASE_SPEED, trim)
        time.sleep(RUN_SECONDS)
        print("Stop")
        drive(pi, 0, trim)
        time.sleep(1)
    finally:
        pi.set_servo_pulsewidth(PIN_L, 0)
        pi.set_servo_pulsewidth(PIN_R, 0)
        pi.stop()


if __name__ == "__main__":
    main()
