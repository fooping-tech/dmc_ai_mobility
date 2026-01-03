# OLED UI モード

OLED の表示を「UI モード」として切り替えられるようにした機能の概要です。  
`oled/cmd` と `oled/image/mono1` の一時上書き表示は従来通り最優先で動作します。

## 優先順位

1) `oled/cmd` / `oled/image/mono1` の一時上書き（`[oled].override_s` 秒）  
2) モード切替アニメ（`mode_switch_frames_dir` が設定されている場合）  
3) UI モード本体（welcome / drive / settings / legacy）

## モード一覧

- `legacy`: 従来の boot/motor 画像表示（後方互換モード）
- `welcome`: ウェルカムアニメ（フレーム列を再生）
- `drive`: 走行モード（モータ指示値 + “目”アニメ）
- `settings`: 設定モード（簡易メニュー表示）

`welcome` は `welcome_loop=false` の場合、再生終了後に `default_mode` へ戻ります。

## 設定（config.toml）

```toml
[oled]
default_mode = "legacy"
welcome_frames_dir = "assets/oled/welcome"
welcome_fps = 10
welcome_loop = false
welcome_on_boot = true
mode_switch_frames_dir = "assets/oled/mode_switch"
mode_switch_fps = 10
eyes_frames_dir = "assets/oled/eyes"
eyes_fps = 10
```

## Zenoh でモード切替

キー: `dmc_robo/<robot_id>/oled/mode`

```json
{
  "mode": "drive",
  "settings_index": 1,
  "ts_ms": 1735467890123
}
```

- `mode`: `legacy`/`welcome`/`drive`/`settings`
- `settings_index`: settings モードの選択位置（0 始まり、任意）

例:

```bash
python3 examples/remote_zenoh_tool.py \
  --robot-id rasp-zero-01 \
  --zenoh-config ./zenoh_remote.json5 \
  oled-mode --mode drive
```

## アニメーション assets の構成

`welcome` / `mode_switch` / `eyes` はフォルダ内のフレーム列として読み込みます。  
`.bin` でも画像（png/jpg）でも OK です。ファイル名順で再生されます。

例:

```
assets/oled/welcome/frame_000.bin
assets/oled/welcome/frame_001.bin
assets/oled/mode_switch/frame_000.bin
assets/oled/eyes/frame_000.bin
```

## 事前レンダリング（連番画像 -> .bin）

```bash
python3 tools/oled_preview/render_oled_sequence.py \
  --in-dir ./assets/oled_src/welcome \
  --out-dir ./assets/oled/welcome \
  --width 128 \
  --height 32
```

## 備考

- `drive` / `settings` は PIL を使ってテキスト描画するため、`pillow` が必要です。
- assets が無い場合はテキスト表示にフォールバックします。
