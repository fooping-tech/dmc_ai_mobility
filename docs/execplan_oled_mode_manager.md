# Refactor OLED UI modes into a mode manager

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Introduce a dedicated OLED mode manager that owns mode registration, transitions, and rendering. This makes it easy to add new UI modes without touching the main robot loop while preserving existing behavior (welcome/mode-switch/drive/settings/legacy).

## Progress

- [x] (2025-01-03) Implement `OledModeManager` with a mode registry and default handlers.
- [x] (2025-01-03) Wire `robot_node.py` to use the manager instead of inline mode logic.
- [x] (2025-01-03) Update docs if needed (internal architecture note).
- [x] (2025-01-03) Add no-hardware validation steps/transcripts.

## Surprises & Discoveries

- Observation: Current mode logic lives directly inside `robot_node.py` with multiple shared mutable variables.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py` contains `oled_mode`/`oled_mode_switch_active`/`oled_welcome_start_ms` etc.

## Decision Log

- Decision: Implement a mode registry inside a dedicated manager and keep override handling in `robot_node.py`.
  Rationale: Keeps the “override wins” behavior intact while making base UI modes easy to extend.
  Date/Author: 2025-01-03 / Codex

## Outcomes & Retrospective

At completion:

- `robot_node.py` delegates base UI rendering to `OledModeManager`.
- New modes can be added by registering a handler in the manager module.
- Existing behavior and Zenoh interfaces remain unchanged.

## Context and Orientation

- OLED rendering loop lives in `src/dmc_ai_mobility/app/robot_node.py`.
- Mono1 conversion and frame sequence helpers live in `src/dmc_ai_mobility/core/oled_ui.py`.
- OLED mode commands come from Zenoh `dmc_robo/<robot_id>/oled/mode`.

## Plan of Work

1) Create `src/dmc_ai_mobility/app/oled_mode_manager.py`:
   - Load assets/sequences from config.
   - Provide `set_mode()` and `render()` APIs.
   - Register default handlers: welcome/drive/settings/legacy.

2) Update `robot_node.py`:
   - Replace inline mode variables with a manager instance.
   - Delegate rendering to `OledModeManager.render()`.
   - Route `oled/mode` commands to `OledModeManager.set_mode()`.

3) Add a small architecture note in `docs/oled_ui_modes.md`.

## Concrete Steps

Run commands from repo root:

1) Update code files as described above.
2) Validate with:
   - `python3 -m py_compile src/dmc_ai_mobility/app/oled_mode_manager.py`

## Validation and Acceptance

- The robot node runs in dry-run without errors.
- OLED mode switching still works through `oled/mode`.
- Existing override behavior remains intact.

## Idempotence and Recovery

- Re-running the changes is safe; all logic is centralized in the manager.
- If assets are missing, the manager falls back to text rendering.

## Artifacts and Notes

No external assets required for no-hardware validation.

## Interfaces and Dependencies

- `OledModeManager` API:
  - `set_mode(mode: str, settings_index: Optional[int] = None, now_ms: Optional[int] = None, use_transition: bool = True) -> None`
  - `render(now_ms: int, motor_cmd: Optional[MotorCmd], motor_cmd_ms: Optional[int], motor_deadman_ms: int) -> None`

Update Note: Marked implementation and validation complete after wiring `OledModeManager` and running py_compile.
