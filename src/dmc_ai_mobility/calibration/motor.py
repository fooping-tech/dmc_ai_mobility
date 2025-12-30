import time
import json
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
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config.toml"
SAVE_PATH = REPO_ROOT / "configs" / "motor_config.json"
DEFAULT_GPIO = {"pin_l": 19, "pin_r": 12, "sw1": 8, "sw2": 7}


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
            "sw1": int(gpio.get("sw1", DEFAULT_GPIO["sw1"])),
            "sw2": int(gpio.get("sw2", DEFAULT_GPIO["sw2"])),
        }
    except FileNotFoundError:
        print(f"Config not found: {path}, using defaults.")
    except Exception as e:
        print(f"Failed to load GPIO config: {e}, using defaults.")
    return DEFAULT_GPIO.copy()


gpio = load_gpio(CONFIG_PATH)
PIN_L = gpio["pin_l"]
PIN_R = gpio["pin_r"]
SW1 = gpio["sw1"]
SW2 = gpio["sw2"]

# パラメータ
BASE_SPEED = 40  # テスト走行速度
TRIM = 0.0       # 補正値 (正なら左寄り、負なら右寄り)

pi = pigpio.pi()

# スイッチ設定
pi.set_mode(SW1, pigpio.INPUT)
pi.set_pull_up_down(SW1, pigpio.PUD_UP)
pi.set_mode(SW2, pigpio.INPUT)
pi.set_pull_up_down(SW2, pigpio.PUD_UP)

def drive(speed, trim):
    # trimを使って左右差をつける
    # trim > 0 : 右モータを減速 (左へ曲がるのを防ぐため右を遅くするイメージ、または左を速く)
    # 簡易的に片方を減速させる方式
    l_factor = 1.0
    r_factor = 1.0
    
    if trim > 0: # 左に曲がりがち -> 右を強く、あるいは左を弱く？
        # ここでは「右モータの係数」として定義
        # trimが正の値 = 左モータが強い = 右の出力を上げる、または左を下げる
        # シンプルに: 左出力 = speed, 右出力 = speed * (1 + trim)
        r_factor = 1.0 + trim
    else:
        l_factor = 1.0 - trim # trimは負なのでプラスになる
    
    # パルス幅変換 (FS90R)
    pw_l = 1500 + (speed * l_factor * 5)
    pw_r = 1500 - (speed * r_factor * 5) # 右は逆転
    
    pi.set_servo_pulsewidth(PIN_L, pw_l)
    pi.set_servo_pulsewidth(PIN_R, pw_r)

print("=== Motor Calibration Mode ===")
print("Running forward...")
print(f"SW1(GPIO{SW1}): Adjust LEFT bias")
print(f"SW2(GPIO{SW2}): Adjust RIGHT bias")
print("BOTH: Save & Exit")

try:
    while True:
        sw1_state = pi.read(SW1)
        sw2_state = pi.read(SW2)

        if sw1_state == 0 and sw2_state == 0:
            print("Saving...")
            break
        
        if sw1_state == 0: # SW1 Pressed
            TRIM += 0.01
            print(f"Trim: {TRIM:.2f} (Left bias increased)")
            time.sleep(0.2)
        elif sw2_state == 0: # SW2 Pressed
            TRIM -= 0.01
            print(f"Trim: {TRIM:.2f} (Right bias increased)")
            time.sleep(0.2)

        drive(BASE_SPEED, TRIM)
        time.sleep(0.05)

    # Save
    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump({"trim": TRIM}, f)
    print(f"Calibration saved to {SAVE_PATH}")

finally:
    pi.set_servo_pulsewidth(PIN_L, 0)
    pi.set_servo_pulsewidth(PIN_R, 0)
    pi.stop()
