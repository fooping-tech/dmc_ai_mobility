# ExecPlan Guide for dmc_ai_mobility

This file defines how to write and maintain an ExecPlan for this repository. An ExecPlan is a design-to-implementation document that a new contributor can follow end-to-end with no other context.

Use an ExecPlan whenever the work is a complex feature, a system change, or a significant refactor. For small edits, a full plan is optional.

Before writing any ExecPlan, read `dmc_ai_mobility_software_design.md` and include all relevant details in the plan itself. Do not point to external docs. If the design doc does not cover a needed detail, the plan must resolve the ambiguity and record the choice.

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

ExecPlans for this repository must incorporate the system design described in `dmc_ai_mobility_software_design.md`, including:

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

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `dmc_ai_mobility_software_design.md`.

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
