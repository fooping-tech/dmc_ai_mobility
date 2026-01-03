#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dmc_ai_mobility.core.oled_bitmap import (  # noqa: E402
    mono1_buffer_to_pil_image,
    mono1_buf_len,
    pil_image_to_mono1_buffer,
)


def _require_pillow() -> tuple[object, object, object]:
    try:
        from PIL import Image, ImageOps, ImageTk  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "pillow is required for the OLED animation editor (pip install pillow)"
        ) from e
    return Image, ImageOps, ImageTk


@dataclass
class Segment:
    name: str
    effect: str
    duration_s: float
    start_scale: float
    end_scale: float
    start_x: float
    end_x: float
    start_y: float
    end_y: float
    ease: str


EASE_FUNCS: dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1.0 - (1.0 - t) * (1.0 - t),
    "ease_in_out": lambda t: (0.5 * (2.0 * t) ** 2) if t < 0.5 else 1.0 - 0.5 * (2.0 * (1.0 - t)) ** 2,
}

EFFECTS = (
    "hold",
    "scroll_up",
    "scroll_down",
    "scroll_left",
    "scroll_right",
    "zoom_in",
    "zoom_out",
    "pan_up",
    "pan_down",
    "pan_left",
    "pan_right",
    "custom",
)

BASE_FITS = ("contain", "cover", "original")
RESAMPLES = ("nearest", "lanczos")


def _preset_for(effect: str, *, width: int, height: int) -> dict[str, float]:
    if effect == "scroll_up":
        return {"start_y": float(height), "end_y": 0.0}
    if effect == "scroll_down":
        return {"start_y": 0.0, "end_y": float(height)}
    if effect == "scroll_left":
        return {"start_x": float(width), "end_x": 0.0}
    if effect == "scroll_right":
        return {"start_x": 0.0, "end_x": float(width)}
    if effect == "pan_up":
        return {"start_y": 0.0, "end_y": -float(height) * 0.5}
    if effect == "pan_down":
        return {"start_y": 0.0, "end_y": float(height) * 0.5}
    if effect == "pan_left":
        return {"start_x": 0.0, "end_x": -float(width) * 0.5}
    if effect == "pan_right":
        return {"start_x": 0.0, "end_x": float(width) * 0.5}
    if effect == "zoom_in":
        return {"start_scale": 1.0, "end_scale": 1.2}
    if effect == "zoom_out":
        return {"start_scale": 1.2, "end_scale": 1.0}
    return {}


class OledAnimEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OLED Animation Editor")
        self.geometry("980x640")

        self.base_image = None
        self.base_path: Optional[Path] = None

        self.width_var = tk.IntVar(value=128)
        self.height_var = tk.IntVar(value=32)
        self.fps_var = tk.DoubleVar(value=10.0)
        self.preview_scale_var = tk.IntVar(value=4)
        self.invert_var = tk.BooleanVar(value=False)
        self.dither_var = tk.BooleanVar(value=False)
        self.base_fit_var = tk.StringVar(value="contain")
        self.resample_var = tk.StringVar(value="nearest")
        self.loop_var = tk.BooleanVar(value=True)
        self.export_gif_var = tk.BooleanVar(value=True)

        self.segment_effect_var = tk.StringVar(value="hold")
        self.segment_duration_var = tk.DoubleVar(value=1.0)
        self.segment_start_scale_var = tk.DoubleVar(value=1.0)
        self.segment_end_scale_var = tk.DoubleVar(value=1.0)
        self.segment_start_x_var = tk.DoubleVar(value=0.0)
        self.segment_end_x_var = tk.DoubleVar(value=0.0)
        self.segment_start_y_var = tk.DoubleVar(value=0.0)
        self.segment_end_y_var = tk.DoubleVar(value=0.0)
        self.segment_ease_var = tk.StringVar(value="linear")

        self.timeline_var = tk.IntVar(value=0)
        self.timeline_label_var = tk.StringVar(value="0 / 0")

        self.segments: list[Segment] = []
        self._init_segments()

        self.playing = False
        self.play_after_id: Optional[str] = None
        self.current_frame = 0

        self._preview_photo = None
        self._preview_canvas_id = None

        self._build_ui()
        self._refresh_segments_list()
        self.segments_list.selection_set(0)
        self._load_segment_to_fields(0)
        self._refresh_timeline()
        self._update_preview()

    def _init_segments(self) -> None:
        self.segments = [
            Segment(
                name="Segment 1",
                effect="hold",
                duration_s=1.0,
                start_scale=1.0,
                end_scale=1.0,
                start_x=0.0,
                end_x=0.0,
                start_y=0.0,
                end_y=0.0,
                ease="linear",
            )
        ]

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Button(top, text="Load Image", command=self._on_load_image).pack(side="left")
        ttk.Button(top, text="Load BIN", command=self._on_load_bin).pack(side="left", padx=(6, 0))
        self.path_label = ttk.Label(top, text="(no input)")
        self.path_label.pack(side="left", padx=10)
        ttk.Button(top, text="Export Frames", command=self._on_export).pack(side="right")

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=8, pady=6)

        left = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=(0, 8))

        settings = ttk.LabelFrame(left, text="OLED / Preview")
        settings.pack(fill="x", pady=(0, 8))
        self._add_labeled_entry(settings, "Width", self.width_var, 0)
        self._add_labeled_entry(settings, "Height", self.height_var, 1)
        self._add_labeled_entry(settings, "FPS", self.fps_var, 2)
        self._add_labeled_entry(settings, "Preview scale", self.preview_scale_var, 3)
        ttk.Checkbutton(settings, text="Invert", variable=self.invert_var, command=self._update_preview).grid(
            row=4, column=0, sticky="w", padx=6, pady=2
        )
        ttk.Checkbutton(settings, text="Dither", variable=self.dither_var, command=self._update_preview).grid(
            row=4, column=1, sticky="w", padx=6, pady=2
        )
        ttk.Checkbutton(settings, text="Export GIF", variable=self.export_gif_var).grid(
            row=5, column=0, sticky="w", padx=6, pady=2
        )
        ttk.Label(settings, text="Fit").grid(row=6, column=0, sticky="w", padx=6, pady=2)
        ttk.OptionMenu(
            settings,
            self.base_fit_var,
            self.base_fit_var.get(),
            *BASE_FITS,
            command=lambda _: self._update_preview(),
        ).grid(row=6, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(settings, text="Resample").grid(row=7, column=0, sticky="w", padx=6, pady=2)
        ttk.OptionMenu(
            settings,
            self.resample_var,
            self.resample_var.get(),
            *RESAMPLES,
            command=lambda _: self._update_preview(),
        ).grid(row=7, column=1, sticky="ew", padx=6, pady=2)
        settings.columnconfigure(1, weight=1)

        segments_box = ttk.LabelFrame(left, text="Segments")
        segments_box.pack(fill="both", expand=True, pady=(0, 8))
        self.segments_list = tk.Listbox(segments_box, height=6, exportselection=False)
        self.segments_list.pack(fill="both", expand=True, padx=6, pady=6)
        self.segments_list.bind("<<ListboxSelect>>", self._on_segment_select)

        seg_btns = ttk.Frame(segments_box)
        seg_btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(seg_btns, text="Add", command=self._on_add_segment).pack(side="left")
        ttk.Button(seg_btns, text="Remove", command=self._on_remove_segment).pack(side="left", padx=4)
        ttk.Button(seg_btns, text="Up", command=lambda: self._move_segment(-1)).pack(side="left", padx=4)
        ttk.Button(seg_btns, text="Down", command=lambda: self._move_segment(1)).pack(side="left")

        editor = ttk.LabelFrame(left, text="Segment Editor")
        editor.pack(fill="x")
        ttk.Label(editor, text="Effect").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.OptionMenu(editor, self.segment_effect_var, self.segment_effect_var.get(), *EFFECTS, command=lambda _: self._apply_preset()).grid(
            row=0, column=1, sticky="ew", padx=6, pady=2
        )
        ttk.Label(editor, text="Ease").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.OptionMenu(editor, self.segment_ease_var, self.segment_ease_var.get(), *EASE_FUNCS.keys()).grid(
            row=1, column=1, sticky="ew", padx=6, pady=2
        )
        self._add_labeled_entry(editor, "Duration (s)", self.segment_duration_var, 2)
        self._add_labeled_entry(editor, "Start scale", self.segment_start_scale_var, 3)
        self._add_labeled_entry(editor, "End scale", self.segment_end_scale_var, 4)
        self._add_labeled_entry(editor, "Start X", self.segment_start_x_var, 5)
        self._add_labeled_entry(editor, "End X", self.segment_end_x_var, 6)
        self._add_labeled_entry(editor, "Start Y", self.segment_start_y_var, 7)
        self._add_labeled_entry(editor, "End Y", self.segment_end_y_var, 8)
        ttk.Button(editor, text="Apply", command=self._apply_segment_changes).grid(
            row=9, column=0, padx=6, pady=6, sticky="ew"
        )
        ttk.Button(editor, text="Preset", command=self._apply_preset).grid(
            row=9, column=1, padx=6, pady=6, sticky="ew"
        )
        editor.columnconfigure(1, weight=1)

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        self.preview_canvas = tk.Canvas(right, width=512, height=128, bg="black")
        self.preview_canvas.pack(fill="both", expand=True, padx=6, pady=6)

        controls = ttk.Frame(right)
        controls.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(controls, text="Play", command=self._on_play).pack(side="left")
        ttk.Button(controls, text="Pause", command=self._on_pause).pack(side="left", padx=4)
        ttk.Button(controls, text="Stop", command=self._on_stop).pack(side="left", padx=4)
        ttk.Checkbutton(controls, text="Loop", variable=self.loop_var).pack(side="left", padx=6)
        ttk.Label(controls, textvariable=self.timeline_label_var).pack(side="right")

        self.timeline_scale = ttk.Scale(
            right,
            from_=0,
            to=0,
            orient="horizontal",
            variable=self.timeline_var,
            command=self._on_timeline_scrub,
        )
        self.timeline_scale.pack(fill="x", padx=6, pady=(0, 6))

    def _add_labeled_entry(self, parent: ttk.Widget, label: str, var: tk.Variable, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
        entry = ttk.Entry(parent, textvariable=var, width=10)
        entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
        entry.bind("<FocusOut>", lambda _e: self._refresh_timeline())
        parent.columnconfigure(1, weight=1)

    def _on_load_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Image, _, _ = _require_pillow()
            img = Image.open(path).convert("L")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return
        self.base_image = img
        self.base_path = Path(path)
        self.path_label.config(text=str(self.base_path))
        self._update_preview()

    def _on_load_bin(self) -> None:
        path = filedialog.askopenfilename(
            title="Select mono1 .bin",
            filetypes=[("Binary", "*.bin"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            data = Path(path).read_bytes()
            expected = mono1_buf_len(width, height)
            if len(data) != expected:
                raise ValueError(
                    f"invalid mono1 buffer length: got={len(data)} expected={expected} ({width}x{height})"
                )
            img = mono1_buffer_to_pil_image(data, width=width, height=height).convert("L")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return
        self.base_image = img
        self.base_path = Path(path)
        self.path_label.config(text=str(self.base_path))
        self._update_preview()

    def _on_add_segment(self) -> None:
        idx = len(self.segments) + 1
        seg = Segment(
            name=f"Segment {idx}",
            effect="hold",
            duration_s=1.0,
            start_scale=1.0,
            end_scale=1.0,
            start_x=0.0,
            end_x=0.0,
            start_y=0.0,
            end_y=0.0,
            ease="linear",
        )
        self.segments.append(seg)
        self._refresh_segments_list()
        self.segments_list.selection_clear(0, tk.END)
        self.segments_list.selection_set(len(self.segments) - 1)
        self._load_segment_to_fields(len(self.segments) - 1)
        self._refresh_timeline()

    def _on_remove_segment(self) -> None:
        idx = self._selected_segment_index()
        if idx is None:
            return
        if len(self.segments) <= 1:
            return
        self.segments.pop(idx)
        self._refresh_segments_list()
        new_idx = max(0, idx - 1)
        self.segments_list.selection_set(new_idx)
        self._load_segment_to_fields(new_idx)
        self._refresh_timeline()

    def _move_segment(self, delta: int) -> None:
        idx = self._selected_segment_index()
        if idx is None:
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.segments):
            return
        self.segments[idx], self.segments[new_idx] = self.segments[new_idx], self.segments[idx]
        self._refresh_segments_list()
        self.segments_list.selection_set(new_idx)
        self._load_segment_to_fields(new_idx)
        self._refresh_timeline()

    def _on_segment_select(self, _event: object) -> None:
        idx = self._selected_segment_index()
        if idx is None:
            return
        self._load_segment_to_fields(idx)

    def _apply_segment_changes(self) -> None:
        idx = self._selected_segment_index()
        if idx is None:
            return
        seg = self.segments[idx]
        seg.effect = self.segment_effect_var.get()
        seg.duration_s = max(0.05, float(self.segment_duration_var.get()))
        seg.start_scale = float(self.segment_start_scale_var.get())
        seg.end_scale = float(self.segment_end_scale_var.get())
        seg.start_x = float(self.segment_start_x_var.get())
        seg.end_x = float(self.segment_end_x_var.get())
        seg.start_y = float(self.segment_start_y_var.get())
        seg.end_y = float(self.segment_end_y_var.get())
        seg.ease = self.segment_ease_var.get()
        self._refresh_segments_list()
        self._refresh_timeline()
        self._update_preview()

    def _apply_preset(self) -> None:
        idx = self._selected_segment_index()
        if idx is None:
            return
        effect = self.segment_effect_var.get()
        width = int(self.width_var.get())
        height = int(self.height_var.get())
        preset = _preset_for(effect, width=width, height=height)
        if "start_scale" in preset:
            self.segment_start_scale_var.set(preset["start_scale"])
        if "end_scale" in preset:
            self.segment_end_scale_var.set(preset["end_scale"])
        if "start_x" in preset:
            self.segment_start_x_var.set(preset["start_x"])
        if "end_x" in preset:
            self.segment_end_x_var.set(preset["end_x"])
        if "start_y" in preset:
            self.segment_start_y_var.set(preset["start_y"])
        if "end_y" in preset:
            self.segment_end_y_var.set(preset["end_y"])
        self._apply_segment_changes()

    def _refresh_segments_list(self) -> None:
        self.segments_list.delete(0, tk.END)
        for idx, seg in enumerate(self.segments, start=1):
            self.segments_list.insert(tk.END, f"{idx}: {seg.effect} ({seg.duration_s:.2f}s)")

    def _load_segment_to_fields(self, idx: int) -> None:
        seg = self.segments[idx]
        self.segment_effect_var.set(seg.effect)
        self.segment_duration_var.set(seg.duration_s)
        self.segment_start_scale_var.set(seg.start_scale)
        self.segment_end_scale_var.set(seg.end_scale)
        self.segment_start_x_var.set(seg.start_x)
        self.segment_end_x_var.set(seg.end_x)
        self.segment_start_y_var.set(seg.start_y)
        self.segment_end_y_var.set(seg.end_y)
        self.segment_ease_var.set(seg.ease)

    def _selected_segment_index(self) -> Optional[int]:
        selection = self.segments_list.curselection()
        if not selection:
            return None
        return int(selection[0])

    def _total_frames(self) -> int:
        fps = float(self.fps_var.get())
        if fps <= 0.0:
            return 1
        total = 0
        for seg in self.segments:
            seg_frames = max(1, int(round(seg.duration_s * fps)))
            total += seg_frames
        return max(1, total)

    def _segment_at(self, frame_idx: int) -> tuple[Segment, int, int]:
        fps = float(self.fps_var.get())
        if fps <= 0.0:
            return self.segments[0], 0, 1
        idx = frame_idx
        for seg in self.segments:
            seg_frames = max(1, int(round(seg.duration_s * fps)))
            if idx < seg_frames:
                return seg, idx, seg_frames
            idx -= seg_frames
        return self.segments[-1], 0, 1

    def _apply_ease(self, t: float, ease: str) -> float:
        func = EASE_FUNCS.get(ease, EASE_FUNCS["linear"])
        return max(0.0, min(1.0, func(t)))

    def _compute_base_scale(self, base_w: int, base_h: int, width: int, height: int) -> float:
        if base_w <= 0 or base_h <= 0:
            return 1.0
        mode = self.base_fit_var.get()
        sx = width / base_w
        sy = height / base_h
        if mode == "contain":
            return min(sx, sy)
        if mode == "cover":
            return max(sx, sy)
        return 1.0

    def _render_frame(self, frame_idx: int):
        Image, ImageOps, _ = _require_pillow()
        width = int(self.width_var.get())
        height = int(self.height_var.get())
        if width <= 0 or height <= 0:
            return Image.new("1", (1, 1))

        base = self.base_image
        if base is None:
            return Image.new("1", (width, height))

        seg, local_idx, seg_frames = self._segment_at(frame_idx)
        t = 1.0 if seg_frames <= 1 else local_idx / float(seg_frames - 1)
        t = self._apply_ease(t, seg.ease)
        scale = seg.start_scale + (seg.end_scale - seg.start_scale) * t
        offset_x = seg.start_x + (seg.end_x - seg.start_x) * t
        offset_y = seg.start_y + (seg.end_y - seg.start_y) * t

        base_scale = self._compute_base_scale(base.width, base.height, width, height)
        scale = max(0.01, float(scale) * base_scale)

        if hasattr(Image, "Resampling"):
            resample_nearest = Image.Resampling.NEAREST
            resample_lanczos = Image.Resampling.LANCZOS
        else:
            resample_nearest = Image.NEAREST
            resample_lanczos = Image.LANCZOS
        resample = resample_nearest if self.resample_var.get() == "nearest" else resample_lanczos
        scaled_w = max(1, int(round(base.width * scale)))
        scaled_h = max(1, int(round(base.height * scale)))
        scaled = base.resize((scaled_w, scaled_h), resample=resample)

        canvas = Image.new("L", (width, height))
        x = int(round((width - scaled_w) / 2 + offset_x))
        y = int(round((height - scaled_h) / 2 + offset_y))
        canvas.paste(scaled, (x, y))

        if self.invert_var.get():
            canvas = ImageOps.invert(canvas)

        if self.dither_var.get():
            mono = canvas.convert("1")
        else:
            dither_none = Image.Dither.NONE if hasattr(Image, "Dither") else Image.NONE
            mono = canvas.convert("1", dither=dither_none)
        return mono

    def _update_preview(self) -> None:
        Image, _, ImageTk = _require_pillow()
        total_frames = self._total_frames()
        if total_frames <= 0:
            return
        frame_idx = min(self.current_frame, total_frames - 1)
        img = self._render_frame(frame_idx).convert("L")
        scale = int(self.preview_scale_var.get())
        scale = max(1, scale)
        if hasattr(Image, "Resampling"):
            resample = Image.Resampling.NEAREST
        else:
            resample = Image.NEAREST
        preview = img.resize((img.width * scale, img.height * scale), resample=resample)
        photo = ImageTk.PhotoImage(preview)
        self._preview_photo = photo
        if self._preview_canvas_id is None:
            self._preview_canvas_id = self.preview_canvas.create_image(0, 0, anchor="nw", image=photo)
        else:
            self.preview_canvas.itemconfigure(self._preview_canvas_id, image=photo)
        self.preview_canvas.config(width=preview.width, height=preview.height)
        self.timeline_label_var.set(f"{frame_idx + 1} / {total_frames}")

    def _refresh_timeline(self) -> None:
        total = self._total_frames()
        self.timeline_scale.configure(to=max(0, total - 1))
        self.current_frame = min(self.current_frame, max(0, total - 1))
        self.timeline_var.set(self.current_frame)
        self._update_preview()

    def _on_timeline_scrub(self, _value: str) -> None:
        try:
            idx = int(float(self.timeline_var.get()))
        except Exception:
            return
        self.current_frame = idx
        self._update_preview()

    def _on_play(self) -> None:
        if self.playing:
            return
        self.playing = True
        self._play_step()

    def _on_pause(self) -> None:
        self.playing = False
        if self.play_after_id:
            self.after_cancel(self.play_after_id)
            self.play_after_id = None

    def _on_stop(self) -> None:
        self._on_pause()
        self.current_frame = 0
        self.timeline_var.set(0)
        self._update_preview()

    def _play_step(self) -> None:
        if not self.playing:
            return
        fps = float(self.fps_var.get())
        if fps <= 0.0:
            fps = 1.0
        total = self._total_frames()
        next_frame = self.current_frame + 1
        if next_frame >= total:
            if self.loop_var.get():
                next_frame = 0
            else:
                self.playing = False
                return
        self.current_frame = next_frame
        self.timeline_var.set(self.current_frame)
        self._update_preview()
        delay_ms = int(round(1000.0 / fps))
        self.play_after_id = self.after(delay_ms, self._play_step)

    def _on_export(self) -> None:
        if self.base_image is None:
            messagebox.showerror("Export Error", "Load an image or .bin first.")
            return
        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return
        out_path = Path(out_dir)
        total = self._total_frames()
        frames = []
        for idx in range(total):
            mono = self._render_frame(idx)
            buf = pil_image_to_mono1_buffer(mono, width=mono.width, height=mono.height)
            (out_path / f"frame_{idx:03d}.bin").write_bytes(buf)
            if self.export_gif_var.get():
                frames.append(mono.convert("L"))
        if self.export_gif_var.get() and frames:
            gif_path = out_path / "preview.gif"
            duration_ms = int(round(1000.0 / max(1.0, float(self.fps_var.get()))))
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration_ms,
                loop=0,
            )
        messagebox.showinfo("Export", f"Wrote {total} frames to {out_path}")


def main() -> int:
    try:
        _require_pillow()
    except Exception as e:
        print(str(e))
        return 1
    app = OledAnimEditor()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
