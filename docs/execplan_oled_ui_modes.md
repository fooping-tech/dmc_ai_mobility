# Add OLED UI modes with pre-rendered animations

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Add OLED UI modes that can play pre-rendered mono1 animations (welcome and mode-switch screens) while also supporting dynamic overlays for drive telemetry and settings menus. The result is a richer OLED experience that can be controlled over Zenoh and verified without hardware (mock driver + dry-run).

## Progress

- [x] (2025-01-03) Draft OLED UI mode schema and state machine (modes, transitions, fallbacks).
- [x] (2025-01-03) Implement animation loading/playback helpers and optional PIL rendering.
- [x] (2025-01-03) Wire new `oled/mode` subscription + UI logic into `robot_node.py`.
- [x] (2025-01-03) Add CLI publish command to `examples/remote_zenoh_tool.py`.
- [x] (2025-01-03) Update docs (`docs/index.md`, `docs/keys_and_payloads.md`, `docs/zenoh_remote_pubsub.md`, `docs/config_guide.md`, new OLED UI doc).
- [ ] (2025-01-03) Add no-hardware validation steps and transcripts.

## Surprises & Discoveries

- Observation: Current OLED base display is “boot/motor image” with temporary Zenoh overrides; it does not have a concept of UI modes yet.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py` uses `boot_mono1` / `motor_mono1` when no override is active.

## Decision Log

- Decision: Introduce a new Zenoh key `dmc_robo/<robot_id>/oled/mode` with a JSON payload to change OLED UI mode and optional selection index.
  Rationale: Keeps UI mode changes explicit and decoupled from the existing `oled/cmd` and `oled/image/mono1` overrides.
  Date/Author: 2025-01-03 / Codex

- Decision: Keep the existing override behavior unchanged (override always wins) and add UI modes as the “base” display state.
  Rationale: Preserves backward compatibility and existing remote override workflows.
  Date/Author: 2025-01-03 / Codex

- Decision: Support pre-rendered animations via folders of mono1 frames (`.bin` or image files) and play them at configurable FPS; dynamic overlays (motor values, settings menu) use PIL at runtime when available.
  Rationale: Meets the pre-render requirement while still allowing live telemetry and menu selection.
  Date/Author: 2025-01-03 / Codex

## Outcomes & Retrospective

At completion:

- A new `oled/mode` command exists to switch OLED UI modes.
- Welcome and mode-switch animations can be pre-rendered and played back.
- Drive mode displays motor command values and an “eyes” animation (if provided).
- Settings mode displays a small menu with a selectable highlight.
- A mock-only validation path exists (no hardware required).

## Context and Orientation

Relevant system constraints from `docs/dmc_ai_mobility_software_design.md`:

- Runtime: Raspberry Pi OS, Python 3.x, systemd.
- Zenoh key naming: `dmc_robo/<robot_id>/<component>/<direction>`.
- OLED uses I2C and currently subscribes to `oled/cmd` (JSON) and `oled/image/mono1` (bytes).
- `src/dmc_ai_mobility/app/robot_node.py` owns the OLED loop and display priority:
  1) temporary override (`[oled].override_s`)
  2) base display (boot/motor images).
- `src/dmc_ai_mobility/core/oled_bitmap.py` defines SSD1306 mono1 buffers and conversions.

Terminology:

- “mono1 buffer”: SSD1306 byte layout where each byte is a vertical 8‑pixel “page” for one x‑column.
- “mode”: a named OLED UI state (welcome, drive, settings, legacy).
- “mode switch screen”: a short animation shown when the mode changes.

## Plan of Work

1) Define a new OLED mode command schema and key:
   - Add `oled/mode` key in `src/dmc_ai_mobility/zenoh/keys.py`.
   - Add schema in `src/dmc_ai_mobility/zenoh/schemas.py`.
   - Add `OledModeCmd` in `src/dmc_ai_mobility/core/types.py`.

2) Add OLED UI configuration and animation loading:
   - Extend `OledConfig` in `src/dmc_ai_mobility/core/config.py` with optional animation directories and FPS.
   - Add a helper module for loading frame sequences and rendering overlays (PIL optional).

3) Update the OLED loop state machine:
   - Keep the current override logic.
   - Add a base UI mode state with transitions:
     - Startup welcome animation (if configured), then default mode.
     - On `oled/mode` command, show mode-switch animation (if configured), then enter target mode.
   - Implement drive mode with motor values + eyes frames (if configured), else fallback to text.
   - Implement settings mode menu (fixed items, highlight selection).
   - Preserve “legacy” boot/motor display when `default_mode=legacy`.

4) Add tooling for pre-rendering:
   - Add a CLI tool to convert a folder of images into mono1 `.bin` frames.

5) Update docs and examples:
   - Add `oled/mode` to `docs/keys_and_payloads.md` and `docs/zenoh_remote_pubsub.md`.
   - Add a new doc that explains OLED UI modes and the animation asset layout.
   - Update `docs/config_guide.md` and `docs/index.md`.
   - Add a new `oled-mode` subcommand to `examples/remote_zenoh_tool.py`.

## Concrete Steps

Run commands from repo root:

1) Add new modules and update config/keys/types.
2) Update `robot_node.py` to use the new UI state machine.
3) Add a pre-render tool under `tools/`.
4) Update docs and examples.
5) Run a dry-run validation:
   - `PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --dry-run --log-all-cmd`
   - Publish a mode change with `python3 examples/remote_zenoh_tool.py ... oled-mode --mode drive`

## Validation and Acceptance

No-hardware path (mock driver):

- Start robot node in dry-run mode and observe “oled loop” log output.
- Publish `oled/mode` and observe the mode change and animation frames being logged by the mock driver.
- Publish `oled/image/mono1` and verify it temporarily overrides the mode display for `[oled].override_s` seconds.

Hardware path:

- On a Pi with SSD1306, provide frame assets and confirm welcome/mode-switch animations play and drive/settings modes render as expected.

## Idempotence and Recovery

- Re-running the tools to generate `.bin` frames overwrites existing files safely.
- If animation assets are missing, the system falls back to text-only display (no crash).
- Mode changes are safe to repeat; the OLED loop is single-threaded and guarded by locks.

## Artifacts and Notes

Expected `oled/mode` payload (example):

    {"mode": "settings", "settings_index": 2, "ts_ms": 1735467890123}

Expected assets layout (example):

    assets/oled/welcome/frame_000.bin
    assets/oled/welcome/frame_001.bin
    assets/oled/mode_switch/frame_000.bin
    assets/oled/eyes/frame_000.bin

## Interfaces and Dependencies

- New Zenoh key: `dmc_robo/<robot_id>/oled/mode`
- Payload: JSON with `mode` (string), `settings_index` (int, optional), `ts_ms` (int, optional).
- Modules:
  - `src/dmc_ai_mobility/app/robot_node.py` (state machine + subscriptions)
  - `src/dmc_ai_mobility/core/oled_bitmap.py` (mono1 conversion helpers, reused)
  - New helper module under `src/dmc_ai_mobility/core/` for animation loading/rendering
  - `examples/remote_zenoh_tool.py` for a publish command
- Dependencies:
  - `pillow` for rendering overlays and converting images; optional but recommended.

Update Note: Marked implementation and documentation steps complete after adding OLED UI modes, assets tooling, and Zenoh command support.
