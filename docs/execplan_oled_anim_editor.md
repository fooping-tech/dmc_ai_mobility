# Add OLED animation editor (web)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at the repository root. It also incorporates the relevant design details from `docs/dmc_ai_mobility_software_design.md`.

## Purpose / Big Picture

Provide a web-based editor that can load a single image or `.bin` mono1 buffer, author a simple animation from it (timeline segments with motion presets), preview playback, and export SSD1306 mono1 frame files as a ZIP. This enables creating welcome/mode animations without hardware and without writing custom scripts.

## Progress

- [x] (2025-01-03) Define editor UX and segment-based animation model.
- [x] (2025-01-03) Implement web editor under `tools/oled_preview/web_editor/`.
- [x] (2025-01-03) Add documentation and index links.
- [x] (2025-01-03) Add validation steps (no-hardware).

## Surprises & Discoveries

- Observation: Existing tools only convert single images or sequences, no GUI editor exists.
  Evidence: `tools/oled_preview/preview_oled.py`, `tools/oled_preview/render_oled_sequence.py`.

## Decision Log

- Decision: Use a static web app (HTML/CSS/JS) with no backend for the editor.
  Rationale: Avoid Tk/macOS compatibility issues and keep dependencies minimal.
  Date/Author: 2025-01-03 / Codex

- Decision: Implement a simple timeline made of ordered “segments” with motion presets and editable parameters.
  Rationale: Matches the “video editor” mental model without a complex timeline implementation.
  Date/Author: 2025-01-03 / Codex

## Outcomes & Retrospective

At completion:

- A web tool can load a source image/bin, preview animation, and export `.bin` frames.
- Users can adjust FPS, duration per segment, and motion presets.
- A no-hardware validation path exists (preview + export).

## Context and Orientation

Key constraints and modules:

- OLED uses SSD1306 mono1 buffers (`width * height / 8` bytes), see `src/dmc_ai_mobility/core/oled_bitmap.py`.
- OLED render rate is capped by `[oled].max_hz`, but the editor is offline.
- Existing helpers for mono1 conversion live in `src/dmc_ai_mobility/core/oled_bitmap.py`.

Terminology:

- “Segment”: One clip of motion with duration and parameters (scale/offset/easing).
- “Frame”: A single mono1 buffer generated at a target FPS.

## Plan of Work

1) Implement web editor tool:
   - `tools/oled_preview/web_editor/` with `index.html`, `app.js`, `style.css`.
   - Load image/bin, configure width/height, fps, segment list.
   - Preview playback with a scrubber.
   - Export `.bin` frames as ZIP.

2) Document the tool:
   - Add `docs/oled_anim_editor.md`
   - Link from `docs/index.md` and `docs/oled_preview.md`.

3) Validation:
   - Run the editor, load an image, preview, export frames to a folder.

## Concrete Steps

Run commands from repo root:

1) Start editor:
   - `python3 -m http.server --directory tools/oled_preview/web_editor 8000`
2) Open `http://localhost:8000`, load an input image or `.bin`, add segments, preview playback.
3) Export the ZIP and extract to `assets/oled/welcome`.

## Validation and Acceptance

- The web editor loads in a browser with no backend errors.
- Preview updates when scrubber moves.
- Export creates sequential `frame_###.bin` files sized `width * height / 8`.

## Idempotence and Recovery

- Export generates a ZIP that can be extracted to overwrite existing frames.
- Missing dependencies should show a clear error message.

## Artifacts and Notes

Expected output filenames:

    frame_000.bin
    frame_001.bin
    frame_002.bin

## Interfaces and Dependencies

- Browser: local file access + canvas.
- No Python or JS dependencies.

Update Note: Switched the editor design to a static web app to avoid Tk/macOS compatibility issues.
