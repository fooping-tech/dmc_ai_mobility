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

# GPIO PIN
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"
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


gpio = load_gpio(CONFIG_PATH)
PIN_L = gpio["pin_l"]
PIN_R = gpio["pin_r"]

# FS90R仕様 (パルス幅)
STOP = 1500
CW_MAX = 1000  # 時計回り最大 (前進か後退かは取り付けによる)
CCW_MAX = 2000 # 反時計回り最大

pi = pigpio.pi()

if not pi.connected:
    exit()

def set_motor(speed_l, speed_r):
    # speedは -100(full back) 〜 100(full forward) とする
    # 1500 + (speed * 5) でパルス幅計算
    pw_l = STOP + (speed_l * 5)
    pw_r = STOP - (speed_r * 5) # 右モータは物理的に逆向きなので符号反転
    
    pi.set_servo_pulsewidth(PIN_L, pw_l)
    pi.set_servo_pulsewidth(PIN_R, pw_r)

try:
    print("Forward")
    set_motor(30, 30) # 30%出力
    time.sleep(2)
    
    print("Stop")
    set_motor(0, 0)
    time.sleep(1)
    
    print("Backward")
    set_motor(-30, -30)
    time.sleep(2)
    
    print("Turn Right")
    set_motor(30, -30)
    time.sleep(2)

    print("Turn Left")
    set_motor(-30, 30)
    time.sleep(2)

finally:
    print("Stopping motors...")
    set_motor(0, 0)
    pi.set_servo_pulsewidth(PIN_L, 0) # PWM停止
    pi.set_servo_pulsewidth(PIN_R, 0)
    pi.stop()
