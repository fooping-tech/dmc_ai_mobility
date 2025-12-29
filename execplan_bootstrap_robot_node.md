# Bootstrap a runnable `robot_node` with dry-run validation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Implement a runnable baseline of the DMC AI Mobility robot software that matches the design doc: it can subscribe to motor and OLED commands, publish IMU state and camera frames, and enforce a deadman timeout that safely stops the motors when commands stop arriving.

The outcome is demonstrably working on a development machine with no hardware and no Zenoh broker by using a `--dry-run` mode that logs publishes/subscribes and exercises the deadman safety behavior.

## Progress

- [x] (2025-12-29) Create self-contained ExecPlan.
- [x] (2025-12-29) Implement config loading and typed schemas.
- [x] (2025-12-29) Implement Zenoh key helpers and JSON codec.
- [x] (2025-12-29) Implement drivers with mock/dry-run backends.
- [x] (2025-12-29) Implement `robot_node` loop, deadman, and CLI entrypoint.
- [x] (2025-12-29) Add scripts/systemd unit and minimal unit tests.
- [x] (2025-12-29) Validate dry-run behavior from repo root.

## Surprises & Discoveries

- Observation: Most modules under `src/dmc_ai_mobility/` are empty stubs; only `src/dmc_ai_mobility/calibration/*` contains code.
  Evidence: `find src -type f -maxdepth 4 -print0 | xargs -0 wc -l` shows `0` lines for most files.

## Decision Log

- Decision: Provide a `--dry-run` mode that does not require hardware or a Zenoh runtime.
  Rationale: The design doc requires a no-hardware validation path; also local dev environments may not have Zenoh or device libraries installed.
  Date/Author: 2025-12-29 / Codex

- Decision: Use `unittest` (stdlib) for tests.
  Rationale: The repo has no test dependencies configured yet, and `unittest` runs everywhere.
  Date/Author: 2025-12-29 / Codex

## Outcomes & Retrospective

At completion, the repo provides a runnable baseline service and a dry-run acceptance path. Remaining gaps (hardware driver fidelity, performance tuning, real Zenoh deployment config) are documented in this plan and the code.

## Context and Orientation

This repository targets a Raspberry Pi OS runtime (Python 3.x) and uses Zenoh pub/sub for robot I/O.

Key concepts from `dmc_ai_mobility_software_design.md`:

- Zenoh keys use the convention `dmc_robo/<robot_id>/<component>/<direction>`.
- Motor commands are subscribed from `dmc_robo/<robot_id>/motor/cmd` with a JSON payload containing `v_l`, `v_r`, `unit`, `deadman_ms`, `seq`, `ts_ms`.
- IMU state is published to `dmc_robo/<robot_id>/imu/state`.
- OLED commands are subscribed from `dmc_robo/<robot_id>/oled/cmd`.
- Camera publishes JPEG bytes to `dmc_robo/<robot_id>/camera/image/jpeg` and metadata to `dmc_robo/<robot_id>/camera/meta`.
- Safety: if motor commands stop (deadman timeout) or Zenoh disconnects, the motors must stop.

Key modules to implement/finish:

- `src/dmc_ai_mobility/app/robot_node.py`: main orchestration loop (subscribe, publish, deadman stop).
- `src/dmc_ai_mobility/drivers/*`: hardware drivers and no-hardware mock backends.
- `src/dmc_ai_mobility/zenoh/*`: session wrapper, key naming, JSON schemas/codec, pub/sub helpers.
- `src/dmc_ai_mobility/core/*`: config, timing, logging, shared types.

## Plan of Work

1. Define typed payloads and config:
   - Implement `src/dmc_ai_mobility/core/config.py` to load `config.toml` (and allow overrides from CLI flags).
   - Implement `src/dmc_ai_mobility/core/types.py` to define:
     - `MotorCmd` (parsed from JSON dict; includes deadman ms)
     - `ImuState`
     - `OledCmd`
     - `CameraMeta`
2. Implement Zenoh key helpers and JSON encoding:
   - Implement `src/dmc_ai_mobility/zenoh/keys.py` with functions that produce the exact keys described in the design doc.
   - Implement `src/dmc_ai_mobility/zenoh/schemas.py` with JSON encode/decode helpers and schema descriptions.
3. Implement drivers and no-hardware backends:
   - `src/dmc_ai_mobility/drivers/motor.py`: `MotorDriver` interface; `MockMotorDriver`; optional `PigpioMotorDriver`.
   - `src/dmc_ai_mobility/drivers/imu.py`: `ImuDriver` interface; `MockImuDriver`; optional MPU-based driver.
   - `src/dmc_ai_mobility/drivers/oled.py`: `OledDriver` interface; `MockOledDriver`; optional hardware driver.
   - `src/dmc_ai_mobility/drivers/camera_v4l2.py`: `CameraDriver` interface; `MockCameraDriver`; optional OpenCV V4L2 driver.
4. Implement Zenoh session and pub/sub wrapper:
   - `src/dmc_ai_mobility/zenoh/session.py`: thin wrapper around the `zenoh` Python package if installed; provide a mock session for `--dry-run`.
   - `src/dmc_ai_mobility/zenoh/pubsub.py`: subscribe callbacks for JSON, publish helpers for bytes/JSON.
5. Implement `robot_node` and CLI:
   - `src/dmc_ai_mobility/app/robot_node.py`: start subscriptions; run IMU and camera publishing loops; enforce deadman.
   - `src/dmc_ai_mobility/app/cli.py`: `dmc-ai-mobility robot` command with `--config`, `--robot-id`, `--dry-run`, `--no-camera`.
6. Add operational artifacts:
   - `scripts/run_robot.sh`: run robot node with config.
   - `systemd/dmc-ai-mobility.service`: systemd unit (documented, safe defaults).
7. Add unit tests for key correctness and config loading:
   - `tests/test_zenoh_keys.py`: ensure keys match the design convention.
   - `tests/test_config_load.py`: ensure defaults/overrides behave.

## Concrete Steps

From the repository root:

1. Run unit tests:

   python3 -m pip install -e .
   python3 -m unittest discover -s tests

2. Dry-run the robot node (no Zenoh, no hardware):

   PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --robot-id devbot --dry-run --no-camera

   Expected log excerpts (order may vary):

     INFO  dmc_ai_mobility: dry-run mode enabled
     INFO  dmc_ai_mobility: subscribed dmc_robo/devbot/motor/cmd
     INFO  dmc_ai_mobility: subscribed dmc_robo/devbot/oled/cmd
     INFO  dmc_ai_mobility: deadman timeout -> motor stop

## Validation and Acceptance

Acceptance criteria (no hardware):

- The `robot` CLI subcommand starts and remains running in `--dry-run` mode.
- It logs the exact Zenoh keys it would subscribe/publish.
- It enforces deadman safety by issuing a motor stop after `deadman_ms` elapses without motor commands.

Acceptance criteria (with Zenoh and hardware, optional):

- With a running Zenoh router and real drivers enabled, publishing a motor command JSON updates motor outputs until the deadman timeout.
- IMU state is published at the configured rate.
- Camera publishes JPEG bytes and metadata at the configured rate when enabled.

## Idempotence and Recovery

- Code changes are idempotent: re-running tests and re-running the dry-run command should always succeed.
- If `zenoh` or hardware dependencies are missing, the program must either:
  - run successfully in `--dry-run` mode, or
  - fail fast with a clear message that names the missing dependency and how to enable dry-run.

## Artifacts and Notes

- `config.toml` is extended from the initial GPIO-only content to include:
  - `robot_id`, plus `[motor]`, `[imu]`, `[camera]`, `[zenoh]` sections with defaults that match the design doc.
- Transcripts of dry-run execution are captured in logs, not committed.

## Interfaces and Dependencies

Python interfaces that must exist:

- `dmc_ai_mobility.core.config.load_config(path: Path, overrides: dict | None) -> RobotConfig`
- `dmc_ai_mobility.zenoh.keys.*` functions returning `str` keys using `dmc_robo/<robot_id>/...`
- `dmc_ai_mobility.app.robot_node.run_robot(config: RobotConfig) -> int` (returns process exit code)

Optional (hardware/Zenoh) dependencies:

- `zenoh` (Python package) for real pub/sub.
- `pigpio` for motor PWM control.
- `mpu9250_jmdev` for IMU.
- `opencv-python` (`cv2`) for camera V4L2 capture.

Update Note: (2025-12-29) Initial ExecPlan created to bootstrap the empty module stubs into a runnable baseline with a dry-run validation path.
Update Note: (2025-12-29) Implemented core/zenoh modules, drivers, robot/health nodes, scripts/systemd, and stdlib unit tests; updated validation commands to include install and `PYTHONPATH` usage.
