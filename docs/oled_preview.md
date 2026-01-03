# OLED bitmap プレビュー

SSD1306 の mono1 バッファ（`.bin`）や入力画像を、PC 上でプレビューするための簡易ツールです。

## 必要なもの
- `pillow`（`pip install pillow` または `pip install ".[oled]"`）

## 使い方
### 1) `.bin` をプレビュー
```bash
python3 tools/oled_preview/preview_oled.py \
  --bin ./assets/oled/boot.bin \
  --width 128 \
  --height 32 \
  --scale 4 \
  --out ./preview.png
```

### 2) 画像を OLED 形式に変換してプレビュー
```bash
python3 tools/oled_preview/preview_oled.py \
  --image ./some.png \
  --width 128 \
  --height 32 \
  --invert \
  --scale 4 \
  --out ./preview.png
```

### 3) 画像ビューアで直接開く
```bash
python3 tools/oled_preview/preview_oled.py \
  --bin ./assets/oled/boot.bin \
  --width 128 \
  --height 32 \
  --scale 4 \
  --show
```

## 事前レンダリング（アニメ用フレーム生成）

連番画像（png/jpg）を `.bin` フレーム列に変換します。

```bash
python3 tools/oled_preview/render_oled_sequence.py \
  --in-dir ./assets/oled_src/welcome \
  --out-dir ./assets/oled/welcome \
  --width 128 \
  --height 32
```

## GUI エディタ

1枚の画像や `.bin` からアニメーションを作成できる GUI 版ツールがあります。  
詳細は `docs/oled_anim_editor.md` を参照してください。

## 注意
- `height` は 8 の倍数である必要があります（SSD1306 の page 構造に合わせています）。
- `.bin` のサイズは `width * height / 8` bytes に一致する必要があります。
