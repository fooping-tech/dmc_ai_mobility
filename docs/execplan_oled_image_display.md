# Add OLED image modes (boot/motor) + temporary Zenoh override

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Add two OLED display behaviors to the robot node:

1) Normal display: show a prebuilt OLED image for “boot/idle” and switch to another image when the motors are actively commanded.
2) Temporary override: when Zenoh sends OLED data, display it for a configurable duration (default 2s) and then automatically revert to the normal display.

After this change, contributors can verify the behavior without hardware by using `--dry-run`, and can drive the override behavior by publishing to a new Zenoh key.

## Progress

- [x] (2025-12-31) Add mono1 bitmap utilities and OLED driver support for raw mono1 buffers.
- [x] (2025-12-31) Add Zenoh key `oled/image/mono1` and wire a new subscription in `robot_node`.
- [x] (2025-12-31) Add config knobs for `override_s` and base images.
- [x] (2025-12-31) Add remote tool command `oled-image` and update docs/tests.
- [ ] (2025-12-31) Optional: add sample assets under `assets/oled/` (not required for functionality).

## Surprises & Discoveries

- Observation: The existing OLED path was “text-only” and directly updated the hardware from the subscription callback.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py` previously called `oled.show_text()` inside `on_oled_cmd()`.

## Decision Log

- Decision: Introduce a new Zenoh key `dmc_robo/<robot_id>/oled/image/mono1` for raw bytes.
  Rationale: Avoid JSON/base64 overhead and keep the payload small and simple (same style as `camera/image/jpeg`).
  Date/Author: 2025-12-31 / Codex

- Decision: Consolidate OLED rendering into a single `oled_loop` thread.
  Rationale: Prevent competing updates (base display vs. remote override) from overwriting each other.
  Date/Author: 2025-12-31 / Codex

- Decision: Convert image files to mono1 at startup (or accept prebuilt `.bin`) and keep the mono1 bytes in memory.
  Rationale: Matches “convert in advance” intent while keeping runtime updates fast and deterministic.
  Date/Author: 2025-12-31 / Codex

## Outcomes & Retrospective

At completion:

- `robot_node` shows a normal boot/idle image and switches to a motor image when motor commands are active.
- Publishing to `oled/image/mono1` overrides the display for `[oled].override_s` seconds and then reverts.
- The remote sender can publish either a prebuilt `.bin` or an input image to be converted locally.

Known limitations:

- The “motor active” heuristic uses recent motor commands + non-zero velocity, not measured motor current/encoder state.
- The mono1 buffer assumes SSD1306 page layout and `height % 8 == 0`.

## Context and Orientation

Relevant repo concepts and files:

- Robot node orchestration: `src/dmc_ai_mobility/app/robot_node.py`
- OLED driver abstraction: `src/dmc_ai_mobility/drivers/oled.py`
- Config loading (TOML): `src/dmc_ai_mobility/core/config.py`
- Zenoh keys: `src/dmc_ai_mobility/zenoh/keys.py`
- Remote publish tool: `examples/remote_zenoh_tool.py`

Terminology:

- “mono1 buffer”: a raw bytes buffer for SSD1306 where each byte represents a vertical 8-pixel “page” for one x-column.
- “override”: temporary OLED content received via Zenoh that takes priority over normal display.

## Plan of Work

1. Add mono1 buffer utilities for size validation and image conversion.
2. Extend OLED driver interface to render either text or mono1 bytes.
3. Extend config to specify:
   - `[oled].boot_image` / `[oled].motor_image` (optional)
   - `[oled].override_s` (default 2.0)
4. Add Zenoh key `oled/image/mono1` and subscribe to it.
5. In `robot_node`, add a dedicated OLED thread that:
   - renders override content while active
   - otherwise renders boot/motor state content
6. Add a remote tool command to publish mono1 buffers (from `.bin` or input image).
7. Update docs and tests.

## Concrete Steps

From the repository root:

1) (Optional) Create a `.bin` mono1 payload from an input image:

    PYTHONPATH=src python3 scripts/convert_oled_mono1.py --in ./some.png --out ./boot.bin --width 128 --height 32

2) Run unit tests:

    python3 -m unittest discover -s tests

3) Run the robot node in dry-run mode (no hardware, no Zenoh router needed):

    PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --robot-id devbot --dry-run --no-camera

4) In another terminal (also dry-run is fine if both run in the same process; for real Zenoh, use `--zenoh-config`):

    python3 examples/remote_zenoh_tool.py --robot-id devbot --zenoh-config ./zenoh_remote.json5 oled-image --bin ./boot.bin --width 128 --height 32

## Validation and Acceptance

Acceptance (no hardware):

- `--dry-run` starts and logs subscriptions including:
  - `dmc_robo/<robot_id>/oled/cmd`
  - `dmc_robo/<robot_id>/oled/image/mono1`
- Publishing `oled-image` causes OLED updates in logs (mock driver) and after `[oled].override_s` seconds it returns to normal display.

Acceptance (with OLED hardware):

- Boot image appears on start.
- When motor commands are active (non-zero velocities within deadman window), the motor image is shown.
- Publishing `oled/image/mono1` overrides the display for `[oled].override_s` seconds.

## Idempotence and Recovery

- Running `scripts/convert_oled_mono1.py` repeatedly overwrites the same output file safely.
- If an image asset path is invalid, the node falls back to a simple text display and keeps running.

## Artifacts and Notes

- New config keys: `config.toml` `[oled].override_s`, `[oled].boot_image`, `[oled].motor_image`
- New Zenoh key: `dmc_robo/<robot_id>/oled/image/mono1` (bytes)
- Helper script: `scripts/convert_oled_mono1.py`
- Remote publish: `python3 examples/remote_zenoh_tool.py ... oled-image ...`

## Interfaces and Dependencies

- Optional dependency: `pillow` is required for converting input images to mono1 (`--image` path and startup conversions for non-`.bin` assets).
- Hardware OLED dependency remains: `adafruit-blinka` + `adafruit-circuitpython-ssd1306` + `pillow` (see `pyproject.toml` extra `oled`).
- The mono1 buffer size must match `width*height/8` and `height` must be a multiple of 8.

Update Note: (2025-12-31) Added normal boot/motor OLED images and a temporary Zenoh override path via `oled/image/mono1`.

