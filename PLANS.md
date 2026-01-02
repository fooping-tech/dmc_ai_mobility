# ExecPlan Guide for dmc_ai_mobility

This file defines how to write and maintain an ExecPlan for this repository. An ExecPlan is a design-to-implementation document that a new contributor can follow end-to-end with no other context.

Use an ExecPlan whenever the work is a complex feature, a system change, or a significant refactor. For small edits, a full plan is optional.

Before writing any ExecPlan, read `docs/dmc_ai_mobility_software_design.md` and include all relevant details in the plan itself. Do not point to external docs. If the design doc does not cover a needed detail, the plan must resolve the ambiguity and record the choice.

## Non-negotiable requirements

Every ExecPlan must be self-contained. A novice must be able to execute it without prior knowledge of this repository or its history.

Every ExecPlan is a living document. Update it as you make progress, discoveries, and decisions. The plan must remain self-contained after every update.

Every ExecPlan must describe a demonstrably working outcome. It is not enough to change code; the plan must explain how to observe the new behavior.

Every term of art must be defined in plain language at first use. If it appears in this repo, name the file or command where it appears.

## Formatting rules

If the ExecPlan is presented inline (for example, in a chat response), it must be a single fenced code block labeled `md` using triple backticks. Do not nest any other fenced blocks inside it. Use indentation for commands, diffs, or transcripts.

If the ExecPlan is written to a Markdown file and that file contains only the ExecPlan, omit the outer triple backticks.

Use proper Markdown headings. Use two newlines after every heading. Use ordered and unordered lists only when prose would be unclear. Checklists are permitted only in the `Progress` section, where they are mandatory.

## Project-specific expectations

ExecPlans for this repository must incorporate the system design described in `docs/dmc_ai_mobility_software_design.md`, including:

The runtime environment (Raspberry Pi OS, Python 3.x, systemd), the Zenoh pub/sub model, and the robot components (motor, IMU, OLED, camera).

The Zenoh key naming convention (`dmc_robo/<robot_id>/<component>/<direction>`) and the payload schemas used for motor commands and camera metadata. If the plan introduces a new key, define its schema and purpose.

The roles of the main modules under `src/dmc_ai_mobility/`, especially `app/robot_node.py` and the drivers under `drivers/`.

Safety behavior such as deadman timeouts and safe motor stop behavior. If you change or add safety behavior, state the user-visible effect and how to validate it.

If a change depends on hardware, include a no-hardware validation path (a stub driver, a dry-run mode, or a simulator) so a contributor can still verify the change.

## Required sections in every ExecPlan

The sections below must exist in every ExecPlan, in this order. Each section must be updated as work proceeds:

Purpose / Big Picture
Progress
Surprises & Discoveries
Decision Log
Outcomes & Retrospective
Context and Orientation
Plan of Work
Concrete Steps
Validation and Acceptance
Idempotence and Recovery
Artifacts and Notes
Interfaces and Dependencies

## Validation guidance

Always include at least one validation path that a novice can run from the repo root. If automated tests exist, include the exact command and the expected pass/fail behavior. If the change is hardware-facing, include a dry-run or mock mode and expected terminal output. Include short, indented example transcripts so the reader can compare results.

## Update note requirement

Whenever you revise an ExecPlan, append a short note at the bottom describing what changed and why. This makes the plan auditable for future contributors.

## ExecPlan skeleton

```md
# <Short, action-oriented description>

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Explain in a few sentences what someone gains after this change and how they can see it working.

## Progress

Use a list with checkboxes to summarize granular steps. Every stopping point must be documented here.

- [x] (2025-10-01T13:00Z) Example completed step.
- [ ] Example incomplete step.
- [ ] Example partially completed step (completed: X; remaining: Y).

## Surprises & Discoveries

Document unexpected behaviors, bugs, or insights discovered during implementation. Provide concise evidence.

- Observation: ...
  Evidence: ...

## Decision Log

Record every decision made while working on the plan in the format:

- Decision: ...
  Rationale: ...
  Date/Author: ...

## Outcomes & Retrospective

Summarize outcomes, gaps, and lessons learned at major milestones or at completion.

## Context and Orientation

Describe the current state as if the reader knows nothing. Name the key files by full path and define any non-obvious term.

## Plan of Work

Describe, in prose, the sequence of edits and additions. For each edit, name the file and location and what to change.

## Concrete Steps

State the exact commands to run and where to run them (working directory). Include short expected outputs as indented examples.

## Validation and Acceptance

Describe how to start or exercise the system and what to observe. Phrase acceptance as behavior with specific inputs and outputs.

## Idempotence and Recovery

State how steps can be repeated safely. If a step is risky, provide a safe retry or rollback path.

## Artifacts and Notes

Include the most important transcripts, diffs, or snippets as indented examples.

## Interfaces and Dependencies

Be prescriptive. Name the libraries, modules, and services to use and why. Specify the types, classes, and function signatures that must exist at the end of the milestone.

Update Note: <What changed and why.>
```

## ExecPlan: Split LiDAR example and driver (YDLidar)

```md
# Split LiDAR example and driver (YDLidar)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

`src/dmc_ai_mobility/drivers/lidar.py` was previously a standalone script that directly initialized and read a YDLidar device. This change separates concerns:

- Provide a proper LiDAR driver module under `src/dmc_ai_mobility/drivers/lidar.py` with a stable, testable interface and safe resource cleanup.
- Provide a runnable example under `examples/` (renamed from the current script) that demonstrates how to read scans and compute a simple “front distance” metric.

After this change, contributors can:

- Run the LiDAR example on a Raspberry Pi connected to a supported YDLidar unit.
- Run a no-hardware validation path (mock mode) from the repo root to confirm imports, CLI behavior, and basic processing logic.

## Progress

- [x] (2025-12-30) Move/rename the current LiDAR script into `examples/` (`examples/example_lidar_front_distance.py`).
- [x] (2025-12-30) Implement `src/dmc_ai_mobility/drivers/lidar.py` as a driver (config, init, read, close).
- [x] (2025-12-30) Update the example to use the new driver API and add a mock/no-hardware path.
- [x] (2025-12-30) Add lightweight validation (compile/import checks and a mock run transcript).
- [ ] (2025-12-30) Update docs/references that mention LiDAR (only if we introduce any).

## Surprises & Discoveries

- Observation: The original LiDAR example lived under `src/dmc_ai_mobility/drivers/` and used a `sys.path` hack.
  Evidence: Previous contents of `src/dmc_ai_mobility/drivers/lidar.py` (now moved to `examples/example_lidar_front_distance.py`) included `sys.path.append(...)`.
- Observation: The repository already vendors a SWIG wrapper and extension: `src/dmc_ai_mobility/drivers/ydlidar.py` and `src/dmc_ai_mobility/drivers/_ydlidar.so`.
  Evidence: `rg -n "drivers/ydlidar.py|_ydlidar.so"`.
- Observation: Mock mode needs synthetic points (not an empty scan) to demonstrate “Front:” output.
  Evidence: Updated `MockLidarDriver` returns deterministic points near 0 degrees.

## Decision Log

- Decision: The example will import the driver (`dmc_ai_mobility.drivers.lidar`) rather than importing `ydlidar` directly.
  Rationale: Keeps examples stable even if the underlying SDK import path changes; concentrates error handling in the driver.
  Date/Author: 2025-12-30 / Codex

- Decision: The driver will attempt to import the vendored wrapper (`dmc_ai_mobility.drivers.ydlidar`) and will raise a clear `RuntimeError` if the native extension is unavailable.
  Rationale: Avoid ambiguity between a globally installed `ydlidar` package vs the vendored SWIG wrapper; provides a single supported import surface.
  Date/Author: 2025-12-30 / Codex

- Decision: Provide a `MockLidarDriver` that returns an empty scan (or deterministic synthetic points) so the example can run without hardware.
  Rationale: Matches repository expectations that hardware-facing changes include a no-hardware validation path.
  Date/Author: 2025-12-30 / Codex

## Outcomes & Retrospective

At completion:

- `examples/` contains a runnable LiDAR example that demonstrates device I/O and “front distance” computation.
- `src/dmc_ai_mobility/drivers/lidar.py` is a reusable driver with explicit configuration and safe lifecycle management.
- A no-hardware path exists and is documented (mock mode).

## Context and Orientation

Relevant repository concepts and files:

## ExecPlan: Add camera latency measurement (local + remote)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Add a reliable way to measure camera latency both on the robot (capture→publish pipeline) and on a remote host (publish→receive). Contributors should be able to see per-frame latency in `camera/meta` and compute publish→receive latency with a subscription tool when clocks are synchronized (e.g., NTP).

## Progress

- [x] Define latency semantics and fields for `camera/meta`.
- [x] Extend the camera driver interface to capture timing data.
- [x] Publish pipeline latency in `camera/meta`.
- [x] Add a remote latency subscriber tool with graph output and document how to use it.
- [x] Add a no-hardware validation path.
- [x] Update schemas and docs to reflect the new fields.
- [ ] Validate on dry-run and Raspberry Pi hardware.

## Surprises & Discoveries

- Observation: `camera/meta` currently publishes only width/height/fps/seq/ts_ms (publish time) and has no capture timestamp.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py`, `src/dmc_ai_mobility/zenoh/schemas.py`, `docs/keys_and_payloads.md`.
- Observation: `MockCameraDriver` returns `None`, so dry-run currently publishes no camera frames.
  Evidence: `src/dmc_ai_mobility/drivers/camera_v4l2.py`.

## Decision Log

- Decision: Extend `camera/meta` rather than creating a new key for latency.
  Rationale: Backward-compatible and keeps metadata in a single place.
  Date/Author: 2026-01-02 / Codex

- Decision: Include both monotonic-based pipeline latency and wall-clock timestamps.
  Rationale: Monotonic avoids clock jumps for local latency, while wall-clock enables remote publish→receive measurement when time is synchronized.
  Date/Author: 2026-01-02 / Codex

- Decision: Add a remote subscriber tool in `examples/remote_zenoh_tool.py` to compute publish→receive latency.
  Rationale: Keeps remote measurement close to existing Zenoh tooling and avoids introducing a new dependency.
  Date/Author: 2026-01-02 / Codex

- Decision: Use optional matplotlib output for latency graphs in the remote tool.
  Rationale: Provides a standard, lightweight way to plot series while keeping the base tool dependency-free.
  Date/Author: 2026-01-02 / Codex

## Outcomes & Retrospective

At completion:

- `camera/meta` includes capture timestamp, publish timestamp, and pipeline latency.
- A remote tool prints publish→receive latency statistics from `camera/meta`.
- Dry-run produces synthetic frames so latency measurement can be validated without hardware.

## Context and Orientation

Runtime environment:

- Raspberry Pi OS, Python 3.x, systemd (per `docs/dmc_ai_mobility_software_design.md`).

Camera publishing today:

- JPEG bytes are published to `dmc_robo/<robot_id>/camera/image/jpeg`.
- JSON metadata is published to `dmc_robo/<robot_id>/camera/meta` from `src/dmc_ai_mobility/app/robot_node.py`.

Key files:

- `src/dmc_ai_mobility/drivers/camera_v4l2.py` (OpenCV capture + JPEG encoding).
- `src/dmc_ai_mobility/core/timing.py` (`monotonic_ms`, `wall_clock_ms`).
- `src/dmc_ai_mobility/zenoh/keys.py`, `src/dmc_ai_mobility/zenoh/schemas.py`.
- `examples/remote_zenoh_tool.py` (Zenoh subscriber tool).
- `docs/keys_and_payloads.md`, `docs/zenoh_remote_pubsub.md` (user-facing schema docs).

Terms:

- Pipeline latency: capture→publish duration measured on the robot.
- Publish-to-remote latency: publish→remote-receive duration (requires synchronized clocks).

## Plan of Work

1) Extend the camera driver interface to return timing metadata.
   - Introduce a `CameraFrame` dataclass with `jpeg`, `width`, `height`, `capture_wall_ms`, `capture_mono_ms`, and `encode_ms` (or `encode_mono_ms`).
   - Update `CameraDriver.read_jpeg()` to return `CameraFrame | None`.
   - Update `MockCameraDriver` to emit synthetic frames with timestamps for dry-run.

2) Update the camera loop in `src/dmc_ai_mobility/app/robot_node.py`.
   - Compute `publish_wall_ms` and `publish_mono_ms` at publish time.
   - Add fields to `camera/meta`: `capture_ts_ms`, `publish_ts_ms`, `pipeline_ms`, `capture_mono_ms`, `publish_mono_ms`,
     `capture_start_mono_ms`, `capture_end_mono_ms`, `read_ms`.
   - Preserve existing fields (`width`, `height`, `fps`, `seq`, `ts_ms`) for backward compatibility.

3) Add a remote latency measurement command in `examples/remote_zenoh_tool.py`.
   - Subscribe to `camera/meta`, compute `publish_to_remote_ms = recv_wall_ms - publish_ts_ms`.
   - Print rolling stats (min/avg/p50/p95) and per-sample line.
   - Render a graph (matplotlib) or save a PNG when requested.
   - Document that accurate publish→receive requires time sync (e.g., NTP).

4) Update schemas and docs.
   - Extend `src/dmc_ai_mobility/zenoh/schemas.py` `CAMERA_META_SCHEMA`.
   - Update `docs/keys_and_payloads.md` and `docs/zenoh_remote_pubsub.md` with the new fields and usage.
   - Update `docs/index.md` if it lists camera meta fields.

5) Validate.
   - Dry-run: run robot node with `--dry-run` and confirm new meta fields are published.
   - Remote tool: subscribe and confirm publish→receive values.
   - Hardware path: optional validation on Raspberry Pi with camera enabled.

## Concrete Steps

1) Update driver interface and mock in:
   - `src/dmc_ai_mobility/drivers/camera_v4l2.py`

2) Update publish payload in:
   - `src/dmc_ai_mobility/app/robot_node.py`

3) Update schema and docs in:
   - `src/dmc_ai_mobility/zenoh/schemas.py`
   - `docs/keys_and_payloads.md`
   - `docs/zenoh_remote_pubsub.md`
   - `docs/index.md`

4) Extend remote tool in:
   - `examples/remote_zenoh_tool.py`

Example commands (repo root):

    python3 -m dmc_ai_mobility.app.cli robot --dry-run --log-level info
    python3 examples/remote_zenoh_tool.py camera-latency --robot-id rasp-zero-01

## Validation and Acceptance

No-hardware:

- Running the robot in dry-run publishes `camera/meta` with new latency fields.
- Remote tool prints publish→receive latency from the received metadata.
- Remote tool can display or save a graph of pipeline/publish→receive latency.

Hardware:

- `pipeline_ms` is non-zero and stable (expected low tens of ms at 640x480/10fps).
- Publish→receive metrics are plausible and stable when clocks are synchronized.
- Camera size comparison baselines (use consistent lighting and FPS):
  - 160x120 (x-low), 320x240 (low), 640x480 (baseline), 1280x720 (high).
  - Record median and p95 for `pipeline_ms` and publish→receive over >= 100 frames per size.
  - Expect latency to increase monotonically with size; document deviations in `Surprises & Discoveries`.

## Idempotence and Recovery

- Code changes are safe to re-apply; no mutable state migrations.
- Disable camera via `--no-camera` or `[camera].enable = false` if issues arise.
- Revert to previous behavior by removing new fields and the remote command.

## Artifacts and Notes

Example `camera/meta` payload (expanded schema):

    {
      "width": 640,
      "height": 480,
      "fps": 10,
      "seq": 42,
      "ts_ms": 1735467890123,
      "capture_ts_ms": 1735467890110,
      "publish_ts_ms": 1735467890123,
      "pipeline_ms": 13,
      "capture_mono_ms": 123456789,
      "publish_mono_ms": 123456802,
      "capture_start_mono_ms": 123456776,
      "capture_end_mono_ms": 123456789,
      "read_ms": 13
    }

## Interfaces and Dependencies

- `CameraFrame` dataclass in `src/dmc_ai_mobility/drivers/camera_v4l2.py`.
- `CameraDriver.read_jpeg() -> CameraFrame | None`.
- `camera/meta` schema extended with latency fields in `src/dmc_ai_mobility/zenoh/schemas.py`.
- `examples/remote_zenoh_tool.py` new `camera-latency` command with optional matplotlib graph output.
- Optional dependency: `matplotlib` for plotting on the remote host.
- Time sync (NTP) required for accurate publish→receive measurement.

Update Note: Added graph output requirement for the remote latency tool, documented optional matplotlib dependency, and expanded size baselines to include 160x120.
Update Note: Extended the planned camera/meta fields to include capture start/end timing and read_ms for capture-start-based latency measurement.
Update Note: Updated the plan language to publish→receive latency to match the current remote tool output.

- The runtime target is Raspberry Pi OS (Linux) with Python 3.x, as described in `docs/dmc_ai_mobility_software_design.md`.
- Drivers live in `src/dmc_ai_mobility/drivers/` and are used by higher-level nodes (for example `src/dmc_ai_mobility/app/robot_node.py`).
- LiDAR example: `examples/example_lidar_front_distance.py` (demonstration script; runnable with `--mock`).
- Vendored YDLidar Python wrapper: `src/dmc_ai_mobility/drivers/ydlidar.py` and native extension `src/dmc_ai_mobility/drivers/_ydlidar.so`.

Terminology:

- “LiDAR”: a distance sensor that produces a 2D scan (angle + range points).
- “Scan”: one acquisition cycle from the LiDAR containing many points.
- “Front distance”: for this example, the average (or minimum) range within a small angular window around 0 degrees.

## Plan of Work

1. Create the example file in `examples/` by moving the original script:

   - Move `src/dmc_ai_mobility/drivers/lidar.py` to `examples/example_lidar_front_distance.py` (or similar).
   - Remove the `sys.path.append(...)` hack.
   - Convert to a small CLI with arguments (port, baudrate, angular window, mock mode).
   - Update imports to use the new driver module.

2. Implement the LiDAR driver in `src/dmc_ai_mobility/drivers/lidar.py`:

   - Define a `LidarDriver` `Protocol` with `read()` and `close()`.
   - Define `YdLidarConfig` as a `@dataclass(frozen=True)` with fields at least:
     - `serial_port: str` (default `/dev/ttyAMA0`)
     - `serial_baudrate: int` (default `230400`)
     - `scan_frequency_hz: float` (default `7.0`)
     - `min_angle_deg: float`, `max_angle_deg: float` (defaults `-180.0` to `180.0`)
     - `min_range_m: float`, `max_range_m: float` (defaults `0.1` to `16.0`)
     - Other fields from the current script if required by the device (sample rate, single channel, intensity).
   - Define a `LidarPoint` and `LidarScan` dataclass (or simple typed structures) so callers do not need to touch SWIG types.
   - Implement `YdLidarDriver`:
     - On init: call `ydlidar.os_init()`, create `CYdLidar`, apply options, initialize, and `turnOn()`.
     - On `read()`: call `doProcessSimple()` into an internal `LaserScan`, then convert `scan.points` into Python-native points.
     - On failures: return `None` or an empty scan and throttle warnings (similar to `camera_v4l2.py`).
     - On `close()`: call `turnOff()` and `disconnecting()` safely (idempotent).
   - Implement `MockLidarDriver` with deterministic output (empty scan or fixed pattern).

3. Update documentation:

   - Update `docs/calibration.md` only if the example introduces any new configuration files (avoid if not needed).
   - Optionally add a brief LiDAR mention to `README.md` if we want a discoverable “how to run example” entry.

## Concrete Steps

From the repository root:

1. Create/move example:

   - `git mv src/dmc_ai_mobility/drivers/lidar.py examples/example_lidar_front_distance.py`

2. Create the new driver module:

   - Create `src/dmc_ai_mobility/drivers/lidar.py` with the driver API described above.

3. Validate in no-hardware mode:

   - `PYTHONPATH=src python3 -m compileall -q src/dmc_ai_mobility examples`
   - `PYTHONPATH=src python3 examples/example_lidar_front_distance.py --mock`

   Expected output example (mock):
     LiDAR Running (mock)
     Front: ... m (Samples: ...)

4. Validate on hardware (Raspberry Pi + LiDAR connected):

   - `PYTHONPATH=src python3 examples/example_lidar_front_distance.py --port /dev/ttyAMA0 --baud 230400`

   Expected output example (hardware):
     LiDAR Running! (Press Ctrl+C to stop)
     Front: 0.532 m (Samples: 14)

## Validation and Acceptance

Acceptance criteria:

- Running the example in mock mode works on any machine (no `ydlidar` dependency required) and prints periodic “Front:” lines.
- Running the example on Raspberry Pi with a connected LiDAR produces periodic “Front:” lines without crashing.
- The new driver exposes a minimal, stable API (`YdLidarDriver.read()` and `.close()`) and does not require `sys.path` hacks.
- Closing the driver is safe to call multiple times and does not leave the LiDAR running.

## Idempotence and Recovery

- Moving files is safe to re-run if done with `git mv`; if a move is wrong, revert with `git checkout -- <path>` or move back.
- If LiDAR initialization fails on hardware, the example should exit with a non-zero status and a clear message indicating missing device, permissions, or SDK.
- Mock mode always remains available as the fallback validation path.

## Artifacts and Notes

Keep one short transcript for:

- Mock run on a dev machine.
- Hardware run on a Raspberry Pi (including the port used and at least one “Front:” line).

Mock run transcript (dev machine):

  PYTHONPATH=src python3 -u examples/example_lidar_front_distance.py --mock --hz 5
  LiDAR Running (mock) (Press Ctrl+C to stop)
  Front(mean): 0.600 m  (Samples: 1)

## Interfaces and Dependencies

Dependencies:

- YDLidar SDK Python bindings, via the vendored wrapper `src/dmc_ai_mobility/drivers/ydlidar.py` and native extension `src/dmc_ai_mobility/drivers/_ydlidar.so`.
- No additional third-party libraries are required for the mock mode.

Interfaces to implement:

- `class LidarDriver(Protocol):`
  - `def read(self) -> LidarScan | None: ...`
  - `def close(self) -> None: ...`
- `@dataclass(frozen=True) class YdLidarConfig: ...`
- `class YdLidarDriver(LidarDriver): ...`
- `class MockLidarDriver(LidarDriver): ...`

Update Note: Initial ExecPlan added to `PLANS.md` to cover splitting the existing LiDAR script into an example and implementing a reusable driver.
Update Note: Implemented the move to `examples/`, added `src/dmc_ai_mobility/drivers/lidar.py` driver API with `YdLidarDriver`/`MockLidarDriver`, and validated mock execution.
Update Note: Refreshed plan wording (past tense / current file locations) so the ExecPlan remains accurate after implementation.
```

## ExecPlan: Add optional LiDAR support to robot node

```md
# Add optional LiDAR support to robot node

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Add LiDAR support to the integrated robot node (`src/dmc_ai_mobility/app/robot_node.py`) so the robot can publish LiDAR data over Zenoh, while keeping LiDAR optional and controllable via `config.toml`.

After this change:

- If `[lidar].enable = true`, the robot node starts a LiDAR loop thread and publishes LiDAR data.
- If `[lidar].enable = false` (default), LiDAR is not initialized and no LiDAR threads are created.
- A no-hardware validation path exists (dry-run / mock driver) so contributors can verify behavior without a connected LiDAR.

## Progress

- [x] (2025-12-30) Add `[lidar]` section to `config.toml` and parse it in `src/dmc_ai_mobility/core/config.py`.
- [x] (2025-12-30) Add Zenoh keys for LiDAR in `src/dmc_ai_mobility/zenoh/keys.py` and document payload shape.
- [x] (2025-12-30) Update `src/dmc_ai_mobility/app/robot_node.py` to initialize LiDAR driver conditionally and publish in a loop thread.
- [x] (2025-12-30) Add no-hardware validation path (mock LiDAR in dry-run when `[lidar].enable=true`).
- [x] (2025-12-30) Update README/docs and `doc/keys_and_payloads.md` with how to enable LiDAR and what topics are published.

## Surprises & Discoveries

- Observation: `robot_node.py` already uses per-device threads (IMU loop and camera loop) and publishes JSON/bytes via Zenoh helpers.
  Evidence: `src/dmc_ai_mobility/app/robot_node.py` has `imu_loop()` + `camera_loop()` and uses `publish_json(...)` / `session.publish(...)`.
- Observation: A LiDAR driver module now exists at `src/dmc_ai_mobility/drivers/lidar.py` with both `YdLidarDriver` and `MockLidarDriver`.
  Evidence: `src/dmc_ai_mobility/drivers/lidar.py`.

## Decision Log

- Decision: LiDAR enable/disable is controlled by `[lidar].enable` in `config.toml` and defaults to disabled.
  Rationale: Keeps existing deployments unchanged and prevents accidental serial device access.
  Date/Author: 2025-12-30 / Codex

- Decision: Publish two Zenoh keys for LiDAR:
  - `dmc_robo/<robot_id>/lidar/scan` (Publish, JSON)
  - `dmc_robo/<robot_id>/lidar/front` (Publish, JSON; small summary used by downstream behaviors)
  Rationale: Full scan is useful for mapping/visualization, while `front` stays lightweight for control and monitoring.
  Date/Author: 2025-12-30 / Codex

- Decision: In `dry_run`, LiDAR uses `MockLidarDriver` automatically when `[lidar].enable = true`.
  Rationale: Provides a no-hardware path consistent with other components.
  Date/Author: 2025-12-30 / Codex

## Outcomes & Retrospective

At completion:

- LiDAR publishing is integrated into robot node without impacting non-LiDAR users.
- LiDAR keys and payload schemas are defined and documented.
- Mock mode enables validation on a laptop/workstation.

## Context and Orientation

Key files to modify:

- `config.toml`: Add a `[lidar]` section (enable + serial params + publish rate).
- `src/dmc_ai_mobility/core/config.py`: Extend `RobotConfig` to include `lidar` settings parsed from TOML.
- `src/dmc_ai_mobility/zenoh/keys.py`: Add key functions for LiDAR topics.
- `src/dmc_ai_mobility/app/robot_node.py`: Initialize LiDAR conditionally and publish in a periodic loop thread.
- `src/dmc_ai_mobility/drivers/lidar.py`: Driver API already exists; robot node should use it (no direct SDK access).

Terminology:

- “Zenoh key”: A string topic like `dmc_robo/<robot_id>/camera/image/jpeg` used for publish/subscribe.
- “Scan JSON”: A JSON payload for one LiDAR scan (many points).
- “Front JSON”: A JSON payload summarizing distance near 0 degrees (small, stable schema).

## Plan of Work

1. Configuration (`config.toml` + parser):

   - Add `[lidar]` section to `config.toml` with defaults:
     - `enable = false`
     - `port = "/dev/ttyAMA0"`
     - `baudrate = 230400`
     - `publish_hz = 10.0`
     - `front_window_deg = 10.0`
     - `front_stat = "mean"` (or `"min"`)
   - Update `src/dmc_ai_mobility/core/config.py` to parse those fields into a new `LidarConfig` dataclass under `RobotConfig`.

2. Zenoh keys:

   - Update `src/dmc_ai_mobility/zenoh/keys.py`:
     - `def lidar_scan(robot_id: str) -> str: return f"dmc_robo/<robot_id>/lidar/scan"`
     - `def lidar_front(robot_id: str) -> str: return f"dmc_robo/<robot_id>/lidar/front"`

3. Robot node integration:

   - In `src/dmc_ai_mobility/app/robot_node.py`:
     - Create `lidar = MockLidarDriver()` by default.
     - If not `dry_run` and `config.lidar.enable`:
       - Initialize `YdLidarDriver(YdLidarConfig(serial_port=..., serial_baudrate=...))`.
       - If init fails, log and keep LiDAR disabled (no thread).
     - Start a `lidar_loop()` thread only when enabled:
       - Use `PeriodicSleeper(config.lidar.publish_hz)`.
       - Call `lidar.read()` and if a scan exists:
         - Publish full scan JSON to `keys.lidar_scan(robot_id)` using `publish_json(...)`.
         - Compute front window metric and publish to `keys.lidar_front(robot_id)` using `publish_json(...)`.
       - Include `seq` and `ts_ms` fields for ordering and timing.
     - Ensure shutdown path closes lidar and joins thread (mirroring camera cleanup patterns).

4. Payload schemas (define explicitly):

   - `lidar/scan` (JSON):
     - `{"seq": <int>, "ts_ms": <int>, "points": [{"angle_rad": <float>, "range_m": <float>, "intensity": <float|null>}, ...]}`
   - `lidar/front` (JSON):
     - `{"seq": <int>, "ts_ms": <int>, "window_deg": <float>, "stat": "mean"|"min", "distance_m": <float>, "samples": <int>}`

5. Docs:

   - Update `README.md` to describe `[lidar]` config and Zenoh keys (and mention mock/dry-run behavior).
   - Update `doc/keys_and_payloads.md` to include the new LiDAR keys and payload schemas.

## Concrete Steps

From the repository root:

1. Update configuration:

   - Edit `config.toml` to include a `[lidar]` section with defaults.
   - Edit `src/dmc_ai_mobility/core/config.py` to parse it into `RobotConfig`.

2. Update keys:

   - Edit `src/dmc_ai_mobility/zenoh/keys.py` to add `lidar_scan()` and `lidar_front()`.

3. Implement node integration:

   - Edit `src/dmc_ai_mobility/app/robot_node.py` to conditionally start the LiDAR thread and publish.

4. Validate without hardware:

   - `PYTHONPATH=src python3 -m compileall -q src/dmc_ai_mobility examples`
   - `PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --dry-run --robot-id devbot`

   Expected log/output characteristics (example; exact formatting may differ):
     robot node started (robot_id=devbot)
     ... published dmc_robo/devbot/lidar/front ...

5. Validate on hardware:

   - Enable LiDAR in `config.toml` and run:
     `./scripts/run_robot.sh`

   Expected behavior:
     - LiDAR thread starts, and Zenoh publishes on `dmc_robo/<robot_id>/lidar/scan` and `.../lidar/front`.

## Validation and Acceptance

Acceptance criteria:

- With `[lidar].enable=false`, robot node starts and runs with no LiDAR initialization attempt and no LiDAR thread.
- With `[lidar].enable=true` + `--dry-run`, robot node publishes mock LiDAR data (at least `lidar/front`) without hardware.
- With `[lidar].enable=true` on hardware, robot node publishes LiDAR data without crashing and cleans up on shutdown.
- Added Zenoh keys follow the naming convention `dmc_robo/<robot_id>/<component>/<direction>`.

## Idempotence and Recovery

- Re-running the robot node repeatedly should not require manual LiDAR reset; `close()` must be safe and best-effort.
- If LiDAR init fails (missing device/permissions), robot node should continue running with LiDAR disabled and a warning log.
- Config defaults keep LiDAR disabled to avoid unintended access to `/dev/tty*`.

## Artifacts and Notes

Keep short transcripts for:

- Dry-run with LiDAR enabled (mock publishing).
- Hardware run showing at least one published LiDAR message.

## Interfaces and Dependencies

Driver dependency:

- Use `src/dmc_ai_mobility/drivers/lidar.py` only (do not import the SDK directly in `robot_node.py`).

Public interfaces introduced/updated:

- `src/dmc_ai_mobility/core/config.py`:
  - `@dataclass(frozen=True) class LidarConfig: ...`
  - `RobotConfig.lidar: LidarConfig`
- `src/dmc_ai_mobility/zenoh/keys.py`:
  - `lidar_scan(robot_id: str) -> str`
  - `lidar_front(robot_id: str) -> str`

Update Note: Initial ExecPlan added to `PLANS.md` for optional LiDAR support in `robot_node.py` controlled via `config.toml`.
Update Note: Implemented optional LiDAR support end-to-end (config parsing, keys, robot node publish loop, and docs updates).
```
