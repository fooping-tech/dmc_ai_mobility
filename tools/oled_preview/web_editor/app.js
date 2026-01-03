const EFFECTS = [
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
  "toon_pop",
  "toon_bounce_up",
  "toon_slide_in",
  "toon_squash",
  "toon_wobble",
  "toon_recoil_in",
  "toon_dash_in",
];

const EASE_FUNCS = {
  linear: (t) => t,
  ease_in: (t) => t * t,
  ease_out: (t) => 1 - (1 - t) * (1 - t),
  ease_in_out: (t) => (t < 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t)),
  back_out: (t) => {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
  elastic_out: (t) => {
    if (t === 0 || t === 1) return t;
    const c4 = (2 * Math.PI) / 3;
    return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
  },
  bounce_out: (t) => {
    const n1 = 7.5625;
    const d1 = 2.75;
    if (t < 1 / d1) {
      return n1 * t * t;
    }
    if (t < 2 / d1) {
      t -= 1.5 / d1;
      return n1 * t * t + 0.75;
    }
    if (t < 2.5 / d1) {
      t -= 2.25 / d1;
      return n1 * t * t + 0.9375;
    }
    t -= 2.625 / d1;
    return n1 * t * t + 0.984375;
  },
};

const els = {
  btnLoadImage: document.getElementById("btnLoadImage"),
  btnLoadBin: document.getElementById("btnLoadBin"),
  fileImage: document.getElementById("fileImage"),
  fileBin: document.getElementById("fileBin"),
  sourceLabel: document.getElementById("sourceLabel"),
  widthInput: document.getElementById("widthInput"),
  heightInput: document.getElementById("heightInput"),
  fpsInput: document.getElementById("fpsInput"),
  scaleInput: document.getElementById("scaleInput"),
  fitSelect: document.getElementById("fitSelect"),
  resampleSelect: document.getElementById("resampleSelect"),
  invertCheck: document.getElementById("invertCheck"),
  ditherCheck: document.getElementById("ditherCheck"),
  loopCheck: document.getElementById("loopCheck"),
  segmentsList: document.getElementById("segmentsList"),
  btnAddSeg: document.getElementById("btnAddSeg"),
  btnRemoveSeg: document.getElementById("btnRemoveSeg"),
  btnUpSeg: document.getElementById("btnUpSeg"),
  btnDownSeg: document.getElementById("btnDownSeg"),
  effectSelect: document.getElementById("effectSelect"),
  easeSelect: document.getElementById("easeSelect"),
  durationInput: document.getElementById("durationInput"),
  startScaleInput: document.getElementById("startScaleInput"),
  endScaleInput: document.getElementById("endScaleInput"),
  startXInput: document.getElementById("startXInput"),
  endXInput: document.getElementById("endXInput"),
  startYInput: document.getElementById("startYInput"),
  endYInput: document.getElementById("endYInput"),
  btnApplySeg: document.getElementById("btnApplySeg"),
  btnPresetSeg: document.getElementById("btnPresetSeg"),
  compositeLabel: document.getElementById("compositeLabel"),
  previewCanvas: document.getElementById("previewCanvas"),
  btnPlay: document.getElementById("btnPlay"),
  btnPause: document.getElementById("btnPause"),
  btnStop: document.getElementById("btnStop"),
  frameLabel: document.getElementById("frameLabel"),
  timeline: document.getElementById("timeline"),
  exportName: document.getElementById("exportName"),
  btnExport: document.getElementById("btnExport"),
  statusLabel: document.getElementById("statusLabel"),
};

const state = {
  baseImage: null,
  baseBin: null,
  baseName: "",
  segments: [],
  selectedSeg: 0,
  currentFrame: 0,
  playing: false,
  playTimer: null,
};

const workCanvas = document.createElement("canvas");
const layerCanvas = document.createElement("canvas");
const monoCanvas = document.createElement("canvas");
const previewCtx = els.previewCanvas.getContext("2d");

function logStatus(text) {
  els.statusLabel.textContent = text;
}

function validateDimensions() {
  const width = Number(els.widthInput.value) || 0;
  const height = Number(els.heightInput.value) || 0;
  if (width <= 0 || height <= 0) {
    logStatus("Width/Height must be > 0.");
    return false;
  }
  if (height % 8 !== 0) {
    logStatus("Height must be a multiple of 8 for SSD1306 mono1.");
    return false;
  }
  return true;
}

function initSegments() {
  state.segments = [
    {
      effect: "hold",
      duration: 1.0,
      startScale: 1.0,
      endScale: 1.0,
      startX: 0.0,
      endX: 0.0,
      startY: 0.0,
      endY: 0.0,
      ease: "linear",
    },
  ];
}

function populateEffects() {
  for (const effect of EFFECTS) {
    const opt = document.createElement("option");
    opt.value = effect;
    opt.textContent = effect;
    els.effectSelect.appendChild(opt);
  }
}

function presetFor(effect, width, height) {
  const presets = {
    scroll_up: { startY: height, endY: 0 },
    scroll_down: { startY: 0, endY: height },
    scroll_left: { startX: width, endX: 0 },
    scroll_right: { startX: 0, endX: width },
    pan_up: { startY: 0, endY: -height * 0.5 },
    pan_down: { startY: 0, endY: height * 0.5 },
    pan_left: { startX: 0, endX: -width * 0.5 },
    pan_right: { startX: 0, endX: width * 0.5 },
    zoom_in: { startScale: 1.0, endScale: 1.2 },
    zoom_out: { startScale: 1.2, endScale: 1.0 },
    toon_pop: { startScale: 0.6, endScale: 1.1, ease: "back_out" },
    toon_bounce_up: { startY: height * 0.6, endY: 0, ease: "bounce_out" },
    toon_slide_in: { startX: width, endX: 0, ease: "back_out" },
    toon_squash: { startScale: 1.25, endScale: 1.0, ease: "elastic_out" },
    toon_wobble: { startScale: 1.0, endScale: 1.0, ease: "linear" },
    toon_recoil_in: {
      startScale: 0.75,
      endScale: 1.0,
      startY: height * 0.25,
      endY: 0,
      ease: "elastic_out",
      duration: 0.6,
    },
    toon_dash_in: {
      startX: width * 1.2,
      endX: 0,
      ease: "back_out",
      duration: 3.0,
    },
  };
  return presets[effect] || {};
}

function compositeInfo(seg) {
  const scale = seg.startScale !== 1 || seg.endScale !== 1;
  const x = seg.startX !== 0 || seg.endX !== 0;
  const y = seg.startY !== 0 || seg.endY !== 0;
  const parts = [];
  if (scale) parts.push("scale");
  if (x) parts.push("x");
  if (y) parts.push("y");
  return {
    count: parts.length,
    label: parts.length ? parts.join(" + ") : "none",
  };
}

function updateCompositeLabel(seg) {
  const info = compositeInfo(seg);
  els.compositeLabel.textContent = `Composite: ${info.label}`;
  if (info.count >= 2) {
    els.compositeLabel.classList.add("composite-on");
  } else {
    els.compositeLabel.classList.remove("composite-on");
  }
}

function totalFrames() {
  const fps = Math.max(1, Number(els.fpsInput.value) || 10);
  let total = 0;
  for (const seg of state.segments) {
    total += Math.max(1, Math.round(seg.duration * fps));
  }
  return Math.max(1, total);
}

function segmentAt(frameIdx) {
  const fps = Math.max(1, Number(els.fpsInput.value) || 10);
  let idx = frameIdx;
  for (const seg of state.segments) {
    const segFrames = Math.max(1, Math.round(seg.duration * fps));
    if (idx < segFrames) {
      return { seg, local: idx, frames: segFrames };
    }
    idx -= segFrames;
  }
  const last = state.segments[state.segments.length - 1];
  return { seg: last, local: 0, frames: 1 };
}

function applyEase(t, ease) {
  const fn = EASE_FUNCS[ease] || EASE_FUNCS.linear;
  return Math.max(0, Math.min(1, fn(t)));
}

function baseFitScale(baseW, baseH, width, height) {
  const fit = els.fitSelect.value;
  if (baseW <= 0 || baseH <= 0) return 1;
  const sx = width / baseW;
  const sy = height / baseH;
  if (fit === "contain") return Math.min(sx, sy);
  if (fit === "cover") return Math.max(sx, sy);
  return 1;
}

function toonModifier(effect, t, width, height) {
  const decay = 1 - t;
  if (effect === "toon_wobble") {
    const ampX = Math.max(1, Math.round(width * 0.02));
    const ampY = Math.max(1, Math.round(height * 0.08));
    const phase = t * Math.PI * 2 * 4;
    return {
      dx: Math.sin(phase) * ampX * decay,
      dy: Math.cos(phase * 1.3) * ampY * decay,
      scale: 1 + Math.sin(phase * 1.7) * 0.05 * decay,
    };
  }
  if (effect === "toon_recoil_in") {
    const phase = t * Math.PI * 2 * 3;
    const ampY = Math.max(1, Math.round(height * 0.12));
    return {
      dx: 0,
      dy: -Math.sin(phase) * ampY * decay,
      scale: 1 + Math.sin(phase) * 0.08 * decay,
    };
  }
  if (effect === "toon_dash_in") {
    const phase = t * Math.PI * 2 * 2;
    const ampX = Math.max(1, Math.round(width * 0.03));
    const lurch = Math.max(1, Math.round(height * 0.08));
    return {
      dx: Math.sin(phase) * ampX * decay,
      dy: Math.sin(Math.PI * t) * lurch * decay,
      scale: 1 + Math.sin(phase) * 0.03 * decay + Math.sin(Math.PI * t) * 0.03 * decay,
    };
  }
  return null;
}

function toonTopKick(effect, localFrame, totalFrames) {
  if (effect !== "toon_dash_in") return 0;
  if (!totalFrames || totalFrames < 4) return 0;
  const kickStart = totalFrames - 3;
  const kickEnd = totalFrames - 2;
  if (localFrame >= kickStart && localFrame <= kickEnd) {
    return 1;
  }
  return 0;
}

function renderFrame(frameIdx) {
  const width = Number(els.widthInput.value) || 128;
  const height = Number(els.heightInput.value) || 32;
  workCanvas.width = width;
  workCanvas.height = height;
  layerCanvas.width = width;
  layerCanvas.height = height;
  monoCanvas.width = width;
  monoCanvas.height = height;

  const ctx = workCanvas.getContext("2d");
  const layerCtx = layerCanvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);
  layerCtx.clearRect(0, 0, width, height);

  if (!state.baseImage) {
    return { buffer: new Uint8Array((width * height) >> 3), monoCanvas };
  }

  const { seg, local, frames } = segmentAt(frameIdx);
  const t = frames <= 1 ? 1 : local / (frames - 1);
  const eased = applyEase(t, seg.ease);

  const baseScale = baseFitScale(state.baseImage.width, state.baseImage.height, width, height);
  const baseSegmentScale = seg.startScale + (seg.endScale - seg.startScale) * eased;
  const scale = Math.max(0.01, baseScale * baseSegmentScale);
  let offsetX = seg.startX + (seg.endX - seg.startX) * eased;
  let offsetY = seg.startY + (seg.endY - seg.startY) * eased;
  let modScale = 1.0;
  const toonMod = toonModifier(seg.effect, eased, width, height);
  if (toonMod) {
    offsetX += toonMod.dx;
    offsetY += toonMod.dy;
    modScale *= toonMod.scale;
  }
  const finalScale = Math.max(0.01, scale * modScale);

  const scaledW = Math.max(1, Math.round(state.baseImage.width * finalScale));
  const scaledH = Math.max(1, Math.round(state.baseImage.height * finalScale));
  layerCtx.imageSmoothingEnabled = els.resampleSelect.value === "smooth";
  if (layerCtx.imageSmoothingEnabled && layerCtx.imageSmoothingQuality) {
    layerCtx.imageSmoothingQuality = "high";
  }
  const drawX = Math.round((width - scaledW) / 2 + offsetX);
  const drawY = Math.round((height - scaledH) / 2 + offsetY);
  layerCtx.drawImage(state.baseImage, drawX, drawY, scaledW, scaledH);

  const kick = toonTopKick(seg.effect, local + 1, frames);
  if (kick > 0) {
    const topHeight = Math.max(1, Math.round(height * 0.45));
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(
      layerCanvas,
      0,
      topHeight,
      width,
      height - topHeight,
      0,
      topHeight,
      width,
      height - topHeight
    );
    ctx.drawImage(
      layerCanvas,
      0,
      0,
      width,
      topHeight,
      -kick,
      0,
      width,
      topHeight
    );
  } else {
    ctx.drawImage(layerCanvas, 0, 0);
  }

  const imgData = ctx.getImageData(0, 0, width, height);
  const { buffer, monoData } = toMono1Buffer(imgData, width, height);
  const monoCtx = monoCanvas.getContext("2d");
  monoCtx.putImageData(monoData, 0, 0);
  return { buffer, monoCanvas };
}

function toMono1Buffer(imgData, width, height) {
  const data = imgData.data;
  const mono = new Uint8Array(width * height);
  const buf = new Uint8Array((width * height) >> 3);
  const invert = els.invertCheck.checked;
  const useDither = els.ditherCheck.checked;
  const bayer = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
  ];
  for (let y = 0; y < height; y++) {
    const page = (y >> 3) * width;
    const bit = y & 7;
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      let luma = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
      if (invert) luma = 255 - luma;
      let threshold = 127;
      if (useDither) {
        const d = bayer[y & 3][x & 3];
        threshold = Math.floor(((d + 0.5) / 16) * 255);
      }
      const on = luma > threshold;
      if (on) {
        buf[page + x] |= 1 << bit;
        mono[y * width + x] = 255;
      } else {
        mono[y * width + x] = 0;
      }
    }
  }
  const monoData = new ImageData(width, height);
  for (let i = 0; i < mono.length; i++) {
    const v = mono[i];
    const j = i * 4;
    monoData.data[j] = v;
    monoData.data[j + 1] = v;
    monoData.data[j + 2] = v;
    monoData.data[j + 3] = 255;
  }
  return { buffer: buf, monoData };
}

function refreshSegmentsList() {
  els.segmentsList.innerHTML = "";
  state.segments.forEach((seg, idx) => {
    const info = compositeInfo(seg);
    const li = document.createElement("li");
    const combo = info.count >= 2 ? " +combo" : "";
    li.textContent = `${idx + 1}: ${seg.effect} (${seg.duration.toFixed(2)}s)${combo}`;
    if (idx === state.selectedSeg) li.classList.add("active");
    li.addEventListener("click", () => {
      state.selectedSeg = idx;
      loadSegmentFields();
      refreshSegmentsList();
    });
    els.segmentsList.appendChild(li);
  });
}

function loadSegmentFields() {
  const seg = state.segments[state.selectedSeg];
  if (!seg) return;
  els.effectSelect.value = seg.effect;
  els.easeSelect.value = seg.ease;
  els.durationInput.value = seg.duration;
  els.startScaleInput.value = seg.startScale;
  els.endScaleInput.value = seg.endScale;
  els.startXInput.value = seg.startX;
  els.endXInput.value = seg.endX;
  els.startYInput.value = seg.startY;
  els.endYInput.value = seg.endY;
  updateCompositeLabel(seg);
}

function applySegmentFields() {
  const seg = state.segments[state.selectedSeg];
  if (!seg) return;
  seg.effect = els.effectSelect.value;
  seg.ease = els.easeSelect.value;
  seg.duration = Math.max(0.05, Number(els.durationInput.value) || 0.5);
  seg.startScale = Number(els.startScaleInput.value) || 1.0;
  seg.endScale = Number(els.endScaleInput.value) || 1.0;
  seg.startX = Number(els.startXInput.value) || 0.0;
  seg.endX = Number(els.endXInput.value) || 0.0;
  seg.startY = Number(els.startYInput.value) || 0.0;
  seg.endY = Number(els.endYInput.value) || 0.0;
  refreshSegmentsList();
  updateCompositeLabel(seg);
  refreshTimeline();
  updatePreview();
}

function applyPreset() {
  const effect = els.effectSelect.value;
  const width = Number(els.widthInput.value) || 128;
  const height = Number(els.heightInput.value) || 32;
  const preset = presetFor(effect, width, height);
  const defaults = {
    startScale: 1.0,
    endScale: 1.0,
    startX: 0.0,
    endX: 0.0,
    startY: 0.0,
    endY: 0.0,
  };
  els.startScaleInput.value = preset.startScale ?? defaults.startScale;
  els.endScaleInput.value = preset.endScale ?? defaults.endScale;
  els.startXInput.value = preset.startX ?? defaults.startX;
  els.endXInput.value = preset.endX ?? defaults.endX;
  els.startYInput.value = preset.startY ?? defaults.startY;
  els.endYInput.value = preset.endY ?? defaults.endY;
  if (preset.duration !== undefined) {
    els.durationInput.value = preset.duration;
  }
  if (preset.ease) {
    els.easeSelect.value = preset.ease;
  }
  applySegmentFields();
}

function refreshTimeline() {
  if (!validateDimensions()) {
    return;
  }
  const total = totalFrames();
  els.timeline.max = Math.max(0, total - 1);
  state.currentFrame = Math.min(state.currentFrame, total - 1);
  els.timeline.value = state.currentFrame;
  updatePreview();
}

function updatePreview() {
  if (!validateDimensions()) {
    return;
  }
  const total = totalFrames();
  if (state.currentFrame >= total) state.currentFrame = total - 1;
  const { monoCanvas } = renderFrame(state.currentFrame);
  const scale = Math.max(1, Number(els.scaleInput.value) || 4);
  els.previewCanvas.width = monoCanvas.width * scale;
  els.previewCanvas.height = monoCanvas.height * scale;
  previewCtx.imageSmoothingEnabled = false;
  previewCtx.clearRect(0, 0, els.previewCanvas.width, els.previewCanvas.height);
  previewCtx.drawImage(monoCanvas, 0, 0, els.previewCanvas.width, els.previewCanvas.height);
  els.frameLabel.textContent = `${state.currentFrame + 1} / ${total}`;
}

function playStep() {
  if (!state.playing) return;
  const fps = Math.max(1, Number(els.fpsInput.value) || 10);
  const total = totalFrames();
  let next = state.currentFrame + 1;
  if (next >= total) {
    if (els.loopCheck.checked) {
      next = 0;
    } else {
      state.playing = false;
      return;
    }
  }
  state.currentFrame = next;
  els.timeline.value = state.currentFrame;
  updatePreview();
  state.playTimer = setTimeout(playStep, Math.round(1000 / fps));
}

function stopPlayback() {
  state.playing = false;
  if (state.playTimer) {
    clearTimeout(state.playTimer);
    state.playTimer = null;
  }
}

function bindEvents() {
  els.btnLoadImage.addEventListener("click", () => els.fileImage.click());
  els.btnLoadBin.addEventListener("click", () => els.fileBin.click());

  els.fileImage.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const img = await loadImageFromFile(file);
    state.baseImage = img;
    state.baseBin = null;
    state.baseName = file.name;
    els.sourceLabel.textContent = file.name;
    logStatus("Loaded image.");
    updatePreview();
  });

  els.fileBin.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const data = new Uint8Array(await file.arrayBuffer());
    const width = Number(els.widthInput.value) || 128;
    const height = Number(els.heightInput.value) || 32;
    const expected = (width * height) >> 3;
    if (data.length !== expected) {
      logStatus(`BIN size mismatch: got ${data.length}, expected ${expected}.`);
      alert("BIN size does not match width/height.");
      return;
    }
    state.baseBin = data;
    state.baseImage = binToCanvasImage(data, width, height);
    state.baseName = file.name;
    els.sourceLabel.textContent = file.name;
    logStatus("Loaded bin.");
    updatePreview();
  });

  [els.widthInput, els.heightInput, els.fpsInput, els.scaleInput].forEach((input) => {
    input.addEventListener("change", () => {
      if (state.baseBin) {
        const width = Number(els.widthInput.value) || 128;
        const height = Number(els.heightInput.value) || 32;
        const expected = (width * height) >> 3;
        if (state.baseBin.length === expected) {
          state.baseImage = binToCanvasImage(state.baseBin, width, height);
        }
      }
      refreshTimeline();
    });
  });

  [els.fitSelect, els.resampleSelect, els.invertCheck, els.ditherCheck].forEach((el) => {
    el.addEventListener("change", () => updatePreview());
  });

  els.btnAddSeg.addEventListener("click", () => {
    state.segments.push({
      effect: "hold",
      duration: 1.0,
      startScale: 1.0,
      endScale: 1.0,
      startX: 0.0,
      endX: 0.0,
      startY: 0.0,
      endY: 0.0,
      ease: "linear",
    });
    state.selectedSeg = state.segments.length - 1;
    refreshSegmentsList();
    loadSegmentFields();
    refreshTimeline();
  });

  els.btnRemoveSeg.addEventListener("click", () => {
    if (state.segments.length <= 1) return;
    state.segments.splice(state.selectedSeg, 1);
    state.selectedSeg = Math.max(0, state.selectedSeg - 1);
    refreshSegmentsList();
    loadSegmentFields();
    refreshTimeline();
  });

  els.btnUpSeg.addEventListener("click", () => moveSegment(-1));
  els.btnDownSeg.addEventListener("click", () => moveSegment(1));

  els.btnApplySeg.addEventListener("click", applySegmentFields);
  els.btnPresetSeg.addEventListener("click", applyPreset);
  els.effectSelect.addEventListener("change", applyPreset);

  els.timeline.addEventListener("input", () => {
    state.currentFrame = Number(els.timeline.value) || 0;
    updatePreview();
  });

  els.btnPlay.addEventListener("click", () => {
    if (state.playing) return;
    state.playing = true;
    playStep();
  });
  els.btnPause.addEventListener("click", () => stopPlayback());
  els.btnStop.addEventListener("click", () => {
    stopPlayback();
    state.currentFrame = 0;
    els.timeline.value = 0;
    updatePreview();
  });

  els.btnExport.addEventListener("click", exportZip);
}

function moveSegment(delta) {
  const idx = state.selectedSeg;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= state.segments.length) return;
  const tmp = state.segments[idx];
  state.segments[idx] = state.segments[newIdx];
  state.segments[newIdx] = tmp;
  state.selectedSeg = newIdx;
  refreshSegmentsList();
  loadSegmentFields();
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}

function binToCanvasImage(buf, width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const imgData = ctx.createImageData(width, height);
  for (let y = 0; y < height; y++) {
    const page = (y >> 3) * width;
    const bit = y & 7;
    for (let x = 0; x < width; x++) {
      const on = (buf[page + x] & (1 << bit)) !== 0;
      const i = (y * width + x) * 4;
      const v = on ? 255 : 0;
      imgData.data[i] = v;
      imgData.data[i + 1] = v;
      imgData.data[i + 2] = v;
      imgData.data[i + 3] = 255;
    }
  }
  ctx.putImageData(imgData, 0, 0);
  return canvas;
}

function exportZip() {
  if (!state.baseImage) {
    alert("Load an image or bin first.");
    return;
  }
  if (!validateDimensions()) {
    alert("Width/Height must be valid (height must be a multiple of 8).");
    return;
  }
  stopPlayback();
  const total = totalFrames();
  const files = [];
  for (let i = 0; i < total; i++) {
    const { buffer } = renderFrame(i);
    const name = `frame_${String(i).padStart(3, "0")}.bin`;
    files.push({ name, data: buffer });
  }
  const zipData = createZip(files);
  const blob = new Blob([zipData], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = els.exportName.value || "oled_frames.zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  logStatus(`Exported ${total} frames.`);
}

function createZip(files) {
  const encoder = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  for (const file of files) {
    const nameBytes = encoder.encode(file.name);
    const data = file.data;
    const crc = crc32(data);
    const localHeader = new Uint8Array(30 + nameBytes.length);
    writeU32(localHeader, 0, 0x04034b50);
    writeU16(localHeader, 4, 20);
    writeU16(localHeader, 6, 0);
    writeU16(localHeader, 8, 0);
    writeU16(localHeader, 10, 0);
    writeU16(localHeader, 12, 0);
    writeU32(localHeader, 14, crc);
    writeU32(localHeader, 18, data.length);
    writeU32(localHeader, 22, data.length);
    writeU16(localHeader, 26, nameBytes.length);
    writeU16(localHeader, 28, 0);
    localHeader.set(nameBytes, 30);
    localParts.push(localHeader, data);

    const central = new Uint8Array(46 + nameBytes.length);
    writeU32(central, 0, 0x02014b50);
    writeU16(central, 4, 20);
    writeU16(central, 6, 20);
    writeU16(central, 8, 0);
    writeU16(central, 10, 0);
    writeU16(central, 12, 0);
    writeU16(central, 14, 0);
    writeU32(central, 16, crc);
    writeU32(central, 20, data.length);
    writeU32(central, 24, data.length);
    writeU16(central, 28, nameBytes.length);
    writeU16(central, 30, 0);
    writeU16(central, 32, 0);
    writeU16(central, 34, 0);
    writeU16(central, 36, 0);
    writeU32(central, 38, 0);
    writeU32(central, 42, offset);
    central.set(nameBytes, 46);
    centralParts.push(central);

    offset += localHeader.length + data.length;
  }
  const centralSize = centralParts.reduce((acc, part) => acc + part.length, 0);
  const centralOffset = offset;
  const end = new Uint8Array(22);
  writeU32(end, 0, 0x06054b50);
  writeU16(end, 4, 0);
  writeU16(end, 6, 0);
  writeU16(end, 8, files.length);
  writeU16(end, 10, files.length);
  writeU32(end, 12, centralSize);
  writeU32(end, 16, centralOffset);
  writeU16(end, 20, 0);

  return concatParts([...localParts, ...centralParts, end]);
}

function concatParts(parts) {
  const total = parts.reduce((acc, p) => acc + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function writeU16(buf, offset, value) {
  buf[offset] = value & 0xff;
  buf[offset + 1] = (value >> 8) & 0xff;
}

function writeU32(buf, offset, value) {
  buf[offset] = value & 0xff;
  buf[offset + 1] = (value >> 8) & 0xff;
  buf[offset + 2] = (value >> 16) & 0xff;
  buf[offset + 3] = (value >> 24) & 0xff;
}

function crc32(bytes) {
  let crc = 0 ^ -1;
  for (let i = 0; i < bytes.length; i++) {
    let c = (crc ^ bytes[i]) & 0xff;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ -1) >>> 0;
}

function init() {
  initSegments();
  populateEffects();
  refreshSegmentsList();
  loadSegmentFields();
  refreshTimeline();
  updatePreview();
  bindEvents();
}

init();
