"""Motor straight calibration (trim) with 4 operating points.

Requested upgrade:
- Calibrate "rotation start command" (v_start) and straight trim at low/mid/high.

Buttons (SW1/SW2):
- SW1 short: + (adjust value)
- SW2 short: - (adjust value)
- BOTH short: cycle mode (START_V -> LOW_TRIM -> MID_TRIM -> HIGH_TRIM)
- BOTH long (>=1.2s): save & exit

Saved file (configs/motor_config.json):
{
  "v_start": 0.10,
  "trim_points": [
    {"label":"low",  "v":0.15, "trim":0.00},
    {"label":"mid",  "v":0.30, "trim":0.00},
    {"label":"high", "v":0.50, "trim":0.00}
  ]
}

Note
- This calibration is applied by robot_node/drivers/motor.py (piecewise trim + v_start).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

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


def load_gpio(path: Path) -> dict:
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

# Motor mapping in m/s units (must match drivers/motor.py defaults)
NEUTRAL_PW = 1500
GAIN_PW_PER_MPS = 500.0


def apply_trim(v_l: float, v_r: float, trim: float) -> tuple[float, float]:
    if not trim:
        return v_l, v_r
    return (v_l * (1.0 - trim), v_r * (1.0 + trim))


def drive(pi: pigpio.pi, v_mps: float, trim: float) -> None:
    v_l, v_r = apply_trim(v_mps, v_mps, trim)
    pw_l = int(NEUTRAL_PW + v_l * GAIN_PW_PER_MPS)
    pw_r = int(NEUTRAL_PW - v_r * GAIN_PW_PER_MPS)  # right inverted
    pi.set_servo_pulsewidth(PIN_L, pw_l)
    pi.set_servo_pulsewidth(PIN_R, pw_r)


@dataclass
class CalState:
    mode: str = "START_V"
    v_start: float = 0.10
    v_low: float = 0.15
    v_mid: float = 0.30
    v_high: float = 0.50
    trim_low: float = 0.00
    trim_mid: float = 0.00
    trim_high: float = 0.00


MODES = ["START_V", "LOW_TRIM", "MID_TRIM", "HIGH_TRIM"]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def main() -> int:
    st = CalState()

    pi = pigpio.pi()

    # Switch config
    for sw in (SW1, SW2):
        pi.set_mode(sw, pigpio.INPUT)
        pi.set_pull_up_down(sw, pigpio.PUD_UP)

    def print_status() -> None:
        print(
            f"MODE={st.mode} | v_start={st.v_start:.2f} | "
            f"low(v={st.v_low:.2f},trim={st.trim_low:+.3f}) "
            f"mid(v={st.v_mid:.2f},trim={st.trim_mid:+.3f}) "
            f"high(v={st.v_high:.2f},trim={st.trim_high:+.3f})",
            flush=True,
        )

    print("=== Motor Straight Calibration (4 points) ===")
    print("SW1 short: + | SW2 short: -")
    print("BOTH short: cycle mode | BOTH long: save & exit")
    print_status()

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
                    break
            else:
                both_press_start = None

            # BOTH short press => cycle mode (rate-limited)
            if both and (now_ms - last_both_cycle_ms) > 1500:
                # cycle once per press
                last_both_cycle_ms = now_ms
                st.mode = MODES[(MODES.index(st.mode) + 1) % len(MODES)]
                print_status()
                time.sleep(0.25)
                continue

            # Per-mode adjustments
            if s1 == 0 and s2 == 1:
                # SW1 short: +
                if st.mode == "START_V":
                    st.v_start = clamp(st.v_start + 0.01, 0.02, 1.00)
                elif st.mode == "LOW_TRIM":
                    st.trim_low = clamp(st.trim_low + 0.01, -0.80, 0.80)
                elif st.mode == "MID_TRIM":
                    st.trim_mid = clamp(st.trim_mid + 0.01, -0.80, 0.80)
                elif st.mode == "HIGH_TRIM":
                    st.trim_high = clamp(st.trim_high + 0.01, -0.80, 0.80)
                print_status()
                time.sleep(debounce_ms / 1000)

            if s2 == 0 and s1 == 1:
                # SW2 short: -
                if st.mode == "START_V":
                    st.v_start = clamp(st.v_start - 0.01, 0.02, 1.00)
                elif st.mode == "LOW_TRIM":
                    st.trim_low = clamp(st.trim_low - 0.01, -0.80, 0.80)
                elif st.mode == "MID_TRIM":
                    st.trim_mid = clamp(st.trim_mid - 0.01, -0.80, 0.80)
                elif st.mode == "HIGH_TRIM":
                    st.trim_high = clamp(st.trim_high - 0.01, -0.80, 0.80)
                print_status()
                time.sleep(debounce_ms / 1000)

            # Drive preview at current mode point
            if st.mode == "START_V":
                drive(pi, st.v_start, st.trim_low)
            elif st.mode == "LOW_TRIM":
                drive(pi, max(st.v_start, st.v_low), st.trim_low)
            elif st.mode == "MID_TRIM":
                drive(pi, max(st.v_start, st.v_mid), st.trim_mid)
            else:
                drive(pi, max(st.v_start, st.v_high), st.trim_high)

            time.sleep(0.05)

        # Save
        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "v_start": float(st.v_start),
            "trim_points": [
                {"label": "low", "v": float(st.v_low), "trim": float(st.trim_low)},
                {"label": "mid", "v": float(st.v_mid), "trim": float(st.trim_mid)},
                {"label": "high", "v": float(st.v_high), "trim": float(st.trim_high)},
            ],
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


if __name__ == "__main__":
    raise SystemExit(main())
