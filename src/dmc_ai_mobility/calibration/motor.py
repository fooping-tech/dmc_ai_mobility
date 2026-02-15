"""Motor straight calibration (trim) with 4 operating points.

Requested upgrade:
- Calibrate "rotation start command" (v_start) and straight trim at low/mid/high.

Buttons (SW1/SW2):
- SW1 short: + (adjust value)
- SW2 short: - (adjust value)
- BOTH short: cycle mode
  STOP_L -> STOP_R
  -> FWD_START_L -> FWD_START_R -> FWD_LOW_TRIM -> FWD_MID_TRIM -> FWD_HIGH_TRIM
  -> REV_START_L -> REV_START_R -> REV_LOW_TRIM -> REV_MID_TRIM -> REV_HIGH_TRIM
- BOTH long (>=1.2s): save & exit

Saved file (configs/motor_config.json):
{
  "neutral_pw_left": 1500,
  "neutral_pw_right": 1500,
  "v_start": 0.10,
  "trim_points": [...],
  "v_start_forward": 0.10,
  "v_start_reverse": 0.10,
  "v_start_left_forward": 0.10,
  "v_start_right_forward": 0.10,
  "v_start_left_reverse": 0.10,
  "v_start_right_reverse": 0.10,
  "trim_points_forward": [...],
  "trim_points_reverse": [...]
}

Note
- This calibration is applied by robot_node/drivers/motor.py (piecewise trim + v_start).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pigpio

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config.toml"
SAVE_PATH = REPO_ROOT / "configs" / "motor_config.json"
DEFAULT_GPIO = {"pin_l": 19, "pin_r": 12, "sw1": 8, "sw2": 7}
DEFAULT_OLED = {"i2c_port": 1, "i2c_address": 0x3C, "width": 128, "height": 32}


def _load_toml(path: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def load_gpio(path: Path) -> dict:
    data = _load_toml(path)
    if not data:
        print(f"Config not found or unreadable: {path}, using GPIO defaults.")
        return DEFAULT_GPIO.copy()
    gpio = data.get("gpio", {})
    return {
        "pin_l": int(gpio.get("pin_l", DEFAULT_GPIO["pin_l"])),
        "pin_r": int(gpio.get("pin_r", DEFAULT_GPIO["pin_r"])),
        "sw1": int(gpio.get("sw1", DEFAULT_GPIO["sw1"])),
        "sw2": int(gpio.get("sw2", DEFAULT_GPIO["sw2"])),
    }


def load_oled(path: Path) -> dict:
    data = _load_toml(path)
    if not data:
        return DEFAULT_OLED.copy()
    o = data.get("oled", {})
    return {
        "i2c_port": int(o.get("i2c_port", DEFAULT_OLED["i2c_port"])),
        "i2c_address": int(o.get("i2c_address", DEFAULT_OLED["i2c_address"])),
        "width": int(o.get("width", DEFAULT_OLED["width"])),
        "height": int(o.get("height", DEFAULT_OLED["height"])),
    }


gpio = load_gpio(CONFIG_PATH)
PIN_L = gpio["pin_l"]
PIN_R = gpio["pin_r"]
SW1 = gpio["sw1"]
SW2 = gpio["sw2"]

oled_cfg = load_oled(CONFIG_PATH)

# Motor mapping in m/s units (must match drivers/motor.py defaults)
NEUTRAL_PW = 1500
GAIN_PW_PER_MPS = 500.0


def apply_trim(v_l: float, v_r: float, trim: float) -> tuple[float, float]:
    if not trim:
        return v_l, v_r
    return (v_l * (1.0 - trim), v_r * (1.0 + trim))


def drive_lr(pi: pigpio.pi, v_l: float, v_r: float) -> None:
    pw_l = int(NEUTRAL_PW + v_l * GAIN_PW_PER_MPS)
    pw_r = int(NEUTRAL_PW - v_r * GAIN_PW_PER_MPS)  # right inverted
    pi.set_servo_pulsewidth(PIN_L, pw_l)
    pi.set_servo_pulsewidth(PIN_R, pw_r)


def drive(pi: pigpio.pi, v_mps: float, trim: float) -> None:
    v_l, v_r = apply_trim(v_mps, v_mps, trim)
    drive_lr(pi, v_l, v_r)


@dataclass
class CalState:
    mode_idx: int = 0
    neutral_l: int = NEUTRAL_PW
    neutral_r: int = NEUTRAL_PW
    v_low: float = 0.15
    v_mid: float = 0.30
    v_high: float = 0.50
    v_start_l_fwd: float = 0.10
    v_start_r_fwd: float = 0.10
    v_start_l_rev: float = 0.10
    v_start_r_rev: float = 0.10
    trim_low_fwd: float = 0.00
    trim_mid_fwd: float = 0.00
    trim_high_fwd: float = 0.00
    trim_low_rev: float = 0.00
    trim_mid_rev: float = 0.00
    trim_high_rev: float = 0.00


MODES = [
    ("NEU", "STOP_L"),
    ("NEU", "STOP_R"),
    ("FWD", "START_L"),
    ("FWD", "START_R"),
    ("FWD", "LOW_TRIM"),
    ("FWD", "MID_TRIM"),
    ("FWD", "HIGH_TRIM"),
    ("REV", "START_L"),
    ("REV", "START_R"),
    ("REV", "LOW_TRIM"),
    ("REV", "MID_TRIM"),
    ("REV", "HIGH_TRIM"),
]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def main() -> int:
    st = CalState()

    pi = pigpio.pi()

    # Switch config
    for sw in (SW1, SW2):
        pi.set_mode(sw, pigpio.INPUT)
        pi.set_pull_up_down(sw, pigpio.PUD_UP)

    oled = None
    try:
        from dmc_ai_mobility.drivers.oled import Ssd1306OledConfig, Ssd1306OledDriver

        oled = Ssd1306OledDriver(
            Ssd1306OledConfig(
                i2c_port=oled_cfg["i2c_port"],
                i2c_address=oled_cfg["i2c_address"],
                width=oled_cfg["width"],
                height=oled_cfg["height"],
            )
        )
    except Exception as e:
        print(f"OLED unavailable in calibration mode: {e}")

    def current_mode() -> tuple[str, str]:
        return MODES[st.mode_idx]

    def _get_trim(direction: str, level: str) -> float:
        if direction == "FWD":
            if level == "LOW_TRIM":
                return st.trim_low_fwd
            if level == "MID_TRIM":
                return st.trim_mid_fwd
            return st.trim_high_fwd
        if level == "LOW_TRIM":
            return st.trim_low_rev
        if level == "MID_TRIM":
            return st.trim_mid_rev
        return st.trim_high_rev

    def _set_trim(direction: str, level: str, value: float) -> None:
        value = clamp(value, -0.80, 0.80)
        if direction == "FWD":
            if level == "LOW_TRIM":
                st.trim_low_fwd = value
            elif level == "MID_TRIM":
                st.trim_mid_fwd = value
            else:
                st.trim_high_fwd = value
        else:
            if level == "LOW_TRIM":
                st.trim_low_rev = value
            elif level == "MID_TRIM":
                st.trim_mid_rev = value
            else:
                st.trim_high_rev = value

    def _get_v_start(direction: str, side: str) -> float:
        if direction == "FWD":
            return st.v_start_l_fwd if side == "L" else st.v_start_r_fwd
        return st.v_start_l_rev if side == "L" else st.v_start_r_rev

    def _set_v_start(direction: str, side: str, value: float) -> None:
        value = clamp(value, 0.02, 1.00)
        if direction == "FWD":
            if side == "L":
                st.v_start_l_fwd = value
            else:
                st.v_start_r_fwd = value
        else:
            if side == "L":
                st.v_start_l_rev = value
            else:
                st.v_start_r_rev = value

    def print_status() -> None:
        d, m = current_mode()
        if m == "STOP_L":
            val = f"neutral_L={st.neutral_l}us"
        elif m == "STOP_R":
            val = f"neutral_R={st.neutral_r}us"
        elif m == "START_L":
            val = f"v_start_L={_get_v_start(d, 'L'):.2f}"
        elif m == "START_R":
            val = f"v_start_R={_get_v_start(d, 'R'):.2f}"
        else:
            val = f"trim={_get_trim(d, m):+.3f}"
        text = (
            f"MODE={d}_{m} | {val} | "
            f"neutral(L/R)={st.neutral_l}/{st.neutral_r}us | "
            f"fwd_start(L/R)={st.v_start_l_fwd:.2f}/{st.v_start_r_fwd:.2f} "
            f"rev_start(L/R)={st.v_start_l_rev:.2f}/{st.v_start_r_rev:.2f} | "
            f"fwd(low/mid/high)={st.trim_low_fwd:+.3f}/{st.trim_mid_fwd:+.3f}/{st.trim_high_fwd:+.3f} | "
            f"rev(low/mid/high)={st.trim_low_rev:+.3f}/{st.trim_mid_rev:+.3f}/{st.trim_high_rev:+.3f}"
        )
        print(text, flush=True)

    def update_oled(emphasis: Optional[str] = None) -> None:
        if oled is None:
            return
        d, m = current_mode()
        line1 = f"CAL {d} {m}"
        if m == "STOP_L":
            line2 = f"nL {st.neutral_l}us"
        elif m == "STOP_R":
            line2 = f"nR {st.neutral_r}us"
        elif m == "START_L":
            line2 = f"vL {_get_v_start(d, 'L'):.2f}"
        elif m == "START_R":
            line2 = f"vR {_get_v_start(d, 'R'):.2f}"
        else:
            line2 = f"trim {_get_trim(d, m):+.3f}"
        line3 = f"SW1+ SW2- BOTH>"
        text = f"{line1}\n{line2}\n{line3}"
        if emphasis:
            text = f"{emphasis}\n{line2}\n{line3}"
        try:
            oled.show_text(text)
        except Exception:
            pass

    print("=== Motor Straight Calibration (dir split) ===")
    print("SW1 short: + | SW2 short: -")
    print("BOTH short: cycle mode | BOTH long: save & exit")
    print_status()
    update_oled()

    both_press_start: int | None = None
    last_both_cycle_ms = 0
    debounce_ms = 180

    try:
        while True:
            now_ms = int(time.monotonic() * 1000)
            s1 = pi.read(SW1)
            s2 = pi.read(SW2)

            both = (s1 == 0 and s2 == 0)

            # Long-press BOTH => save & exit
            if both:
                if both_press_start is None:
                    both_press_start = now_ms
                elif now_ms - both_press_start >= 1200:
                    print("Saving...", flush=True)
                    if oled is not None:
                        try:
                            oled.show_text("CAL\nSAVED")
                        except Exception:
                            pass
                    break
            else:
                both_press_start = None

            # BOTH short press => cycle mode (rate-limited)
            if both and (now_ms - last_both_cycle_ms) > 1500:
                last_both_cycle_ms = now_ms
                st.mode_idx = (st.mode_idx + 1) % len(MODES)
                d, m = current_mode()
                print_status()
                update_oled(emphasis=f"{d} {m}")
                time.sleep(0.25)
                continue

            d, m = current_mode()

            # Per-mode adjustments
            if s1 == 0 and s2 == 1:
                if m == "STOP_L":
                    st.neutral_l = int(clamp(st.neutral_l + 1, 1300, 1700))
                elif m == "STOP_R":
                    st.neutral_r = int(clamp(st.neutral_r + 1, 1300, 1700))
                elif m == "START_L":
                    _set_v_start(d, "L", _get_v_start(d, "L") + 0.01)
                elif m == "START_R":
                    _set_v_start(d, "R", _get_v_start(d, "R") + 0.01)
                else:
                    _set_trim(d, m, _get_trim(d, m) + 0.01)
                print_status()
                update_oled()
                time.sleep(debounce_ms / 1000)

            if s2 == 0 and s1 == 1:
                if m == "STOP_L":
                    st.neutral_l = int(clamp(st.neutral_l - 1, 1300, 1700))
                elif m == "STOP_R":
                    st.neutral_r = int(clamp(st.neutral_r - 1, 1300, 1700))
                elif m == "START_L":
                    _set_v_start(d, "L", _get_v_start(d, "L") - 0.01)
                elif m == "START_R":
                    _set_v_start(d, "R", _get_v_start(d, "R") - 0.01)
                else:
                    _set_trim(d, m, _get_trim(d, m) - 0.01)
                print_status()
                update_oled()
                time.sleep(debounce_ms / 1000)

            # Drive preview at current mode point
            if m == "STOP_L" or m == "STOP_R":
                # apply neutral pulse to inspect stop point drift
                pi.set_servo_pulsewidth(PIN_L, st.neutral_l)
                pi.set_servo_pulsewidth(PIN_R, st.neutral_r)
            else:
                sign = 1.0 if d == "FWD" else -1.0
                if m == "START_L":
                    drive_lr(pi, sign * _get_v_start(d, "L"), 0.0)
                elif m == "START_R":
                    drive_lr(pi, 0.0, sign * _get_v_start(d, "R"))
                else:
                    v_start_avg = max(_get_v_start(d, "L"), _get_v_start(d, "R"))
                    if m == "LOW_TRIM":
                        v_cmd = max(v_start_avg, st.v_low)
                    elif m == "MID_TRIM":
                        v_cmd = max(v_start_avg, st.v_mid)
                    else:
                        v_cmd = max(v_start_avg, st.v_high)
                    drive(pi, sign * v_cmd, _get_trim(d, m))

            time.sleep(0.05)

        # Save
        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        forward_points = [
            {"label": "low", "v": float(st.v_low), "trim": float(st.trim_low_fwd)},
            {"label": "mid", "v": float(st.v_mid), "trim": float(st.trim_mid_fwd)},
            {"label": "high", "v": float(st.v_high), "trim": float(st.trim_high_fwd)},
        ]
        reverse_points = [
            {"label": "low", "v": float(st.v_low), "trim": float(st.trim_low_rev)},
            {"label": "mid", "v": float(st.v_mid), "trim": float(st.trim_mid_rev)},
            {"label": "high", "v": float(st.v_high), "trim": float(st.trim_high_rev)},
        ]
        payload = {
            # backward compatibility
            "v_start": float(max(st.v_start_l_fwd, st.v_start_r_fwd)),
            "trim_points": forward_points,
            # neutral pulse calibration (stop calibration)
            "neutral_pw_left": int(st.neutral_l),
            "neutral_pw_right": int(st.neutral_r),
            # direction-specific aggregate keys
            "v_start_forward": float(max(st.v_start_l_fwd, st.v_start_r_fwd)),
            "v_start_reverse": float(max(st.v_start_l_rev, st.v_start_r_rev)),
            # per-wheel start keys
            "v_start_left_forward": float(st.v_start_l_fwd),
            "v_start_right_forward": float(st.v_start_r_fwd),
            "v_start_left_reverse": float(st.v_start_l_rev),
            "v_start_right_reverse": float(st.v_start_r_rev),
            "trim_points_forward": forward_points,
            "trim_points_reverse": reverse_points,
        }
        with SAVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        print(f"Calibration saved to {SAVE_PATH}")
        return 0

    finally:
        try:
            pi.set_servo_pulsewidth(PIN_L, 0)
            pi.set_servo_pulsewidth(PIN_R, 0)
        finally:
            pi.stop()
        if oled is not None:
            try:
                oled.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
