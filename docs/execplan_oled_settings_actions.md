# Connect OLED settings actions and add a custom mode template

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

The settings UI on the OLED will trigger real actions (calibration, Wi‑Fi connect, git pull, branch switch, shutdown, reboot) instead of only logging a selection. The implementation must work in Raspberry Pi OS, respect systemd operation, and provide a dry‑run/no‑hardware validation path. In addition, provide a template implementation for adding custom OLED modes so new modes can be introduced without modifying the main loop.

## Progress

- [x] Define a settings action runner with safe defaults and a dry‑run path.
- [x] Add new `oled_settings` config section and update config/docs.
- [x] Wire settings actions into `robot_node.py` SW handling.
- [x] Provide scripts for Wi‑Fi connect and branch switch (used by defaults).
- [x] Add a custom mode template helper and document usage.
- [ ] Validate with a dry‑run transcript and update docs/index.md if needed.

## Surprises & Discoveries

- Observation: Current settings selection only logs the chosen item and does not execute any action.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py` logs `settings select: ...` without further processing.

## Decision Log

- Decision: Introduce a dedicated settings action runner that maps OLED menu items to commands, with a cooldown and dry‑run mode.
  Rationale: Keeps button handling responsive while allowing safe execution and a no‑hardware validation path.
  Date/Author: 2025-01-04 / Codex

- Decision: Provide default actions via repo scripts where possible, and allow overrides via `[oled_settings]` in `config.toml`.
  Rationale: Keeps behavior deterministic while allowing per‑robot customization.
  Date/Author: 2025-01-04 / Codex

- Decision: Add a template registration method for custom OLED modes without enabling it by default.
  Rationale: Gives a ready‑to‑use pattern while preserving existing behavior.
  Date/Author: 2025-01-04 / Codex

## Outcomes & Retrospective

At completion:

- Settings menu items trigger real actions or report missing configuration.
- Actions run asynchronously with cooldown and dry‑run support.
- A reusable template exists for adding new OLED UI modes.
- Documentation covers the new config and workflow.

## Context and Orientation

- Runtime: Raspberry Pi OS, Python 3.x, systemd (see `docs/dmc_ai_mobility_software_design.md`).
- OLED UI modes and settings menu are managed by `src/dmc_ai_mobility/app/oled_mode_manager.py`.
- The OLED loop and SW inputs live in `src/dmc_ai_mobility/app/robot_node.py`.
- Existing update workflow uses `scripts/pull_and_restart.sh` (see `docs/deployment.md`).

## Plan of Work

1) Add a settings action runner:
   - Create `src/dmc_ai_mobility/app/oled_settings_actions.py` with:
     - Action constants and a mapping from menu labels to actions.
     - A `OledSettingsActionRunner` that resolves commands, spawns a background thread, and logs results.
     - Dry‑run mode that logs the command instead of executing it.

2) Extend configuration:
   - Add `OledSettingsConfig` in `src/dmc_ai_mobility/core/config.py`.
   - Parse `[oled_settings]` in `load_config`.
   - Update `config.toml` and `docs/config_guide.md` with new settings.

3) Wire into the SW loop:
   - Instantiate the settings action runner in `robot_node.py`.
   - On SW2 short press in settings mode, trigger the action for the selected item.

4) Add default scripts:
   - `scripts/oled_wifi_connect.sh`: uses `nmcli` and env vars (`WIFI_SSID`/`WIFI_PSK`) to connect.
   - `scripts/oled_switch_branch.sh`: checks out a target branch and restarts the service if possible.

5) Provide a template for new modes:
   - Add a helper method or module to register a basic custom mode renderer.
   - Document how to enable it without changing default behavior.

6) Update docs:
   - `docs/oled_ui_modes.md` (settings actions and mapping).
   - `docs/oled_mode_manager.md` (template usage).
   - `docs/config_guide.md` (new `[oled_settings]`).
   - `docs/index.md` if a new doc is added.

## Concrete Steps

From repo root:

1) Edit code and scripts as described above.
2) Run a dry‑run validation:
   - `PYTHONPATH=src python3 - <<'PY'`
     (init config, create runner, call `trigger_item("CALIB")`, observe log)
   - Expected: logs show the action and the command without executing it when `dry_run=True`.

## Validation and Acceptance

- With `--dry-run`, triggering a settings action logs the resolved command and does not execute it.
- With real hardware and permissions, selecting CALIB starts the calibration process, and SHUTDOWN/REBOOT call systemctl.
- Wi‑Fi and branch switch actions execute when `oled_settings` is configured.

## Idempotence and Recovery

- Commands are invoked by separate scripts; re‑running is safe when the underlying command is idempotent.
- If actions fail (e.g., missing permissions), the runner logs the error without crashing the robot node.

## Artifacts and Notes

- Example `[oled_settings]` section in `config.toml`.
- Example log lines showing dry‑run execution.

## Interfaces and Dependencies

- New module: `src/dmc_ai_mobility/app/oled_settings_actions.py`
  - `OledSettingsActionRunner.trigger_item(item: str) -> bool`
- New config section: `[oled_settings]` with command overrides and cooldown.
- Scripts: `scripts/oled_wifi_connect.sh`, `scripts/oled_switch_branch.sh`

Update Note: Initial plan created to connect settings menu selections to actions and provide a custom mode template.
Update Note: Implemented settings actions, scripts, config, and docs; pending dry‑run transcript update.
