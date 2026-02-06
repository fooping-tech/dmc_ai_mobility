# OLED モードマネージャ

`src/dmc_ai_mobility/app/oled_mode_manager.py` は OLED の「UI モード」を管理する専用クラスです。  
`robot_node.py` の OLED ループから呼び出され、モード切替・ウェルカム・設定画面などを描画します。

## 役割

- UI モードの登録・切替・順序管理（welcome/drive/settings/legacy など）
- モード切替アニメーション（`mode_switch_frames_dir`）の再生
- ウェルカムアニメ（`welcome_frames_dir`）の再生
- settings メニューの表示と選択位置の保持

`oled/cmd` や `oled/image/mono1` の一時上書き表示は `robot_node.py` 側で優先的に処理されます。

## デフォルトモード

- `legacy`: 従来の boot/motor 画像
- `welcome`: ウェルカムアニメ
- `drive`: 走行モード（モータ指示値 + 目アニメ）
- `settings`: 設定メニュー

`[oled].default_mode` が不正な場合は `legacy` にフォールバックします。  
`welcome_on_boot=true` かつ welcome フレームが存在する場合、起動時は welcome から始まります。

## 主要 API（抜粋）

- `register_mode(mode, renderer)`  
  UI モードの追加。`renderer(now_ms, motor_cmd, motor_cmd_ms, motor_deadman_ms)` を登録します。
- `register_template_mode(mode="custom")`  
  追加モードのひな形を登録（`CUSTOM\nMODE` の簡易表示）。
- `set_mode(mode, settings_index=None, now_ms=None, use_transition=True)`  
  モード切替。`use_transition` が真で `mode_switch_frames_dir` がある場合は切替アニメ経由。
- `render(now_ms, motor_cmd, motor_cmd_ms, motor_deadman_ms)`  
  OLED ループから毎フレーム呼び出します。
- `cycle_mode(delta, now_ms=None, use_transition=True)`  
  登録順にモードを巡回。
- `step_settings_index(delta)` / `get_settings_item()`  
  settings メニューの選択位置を移動・取得。
- `list_modes()` / `set_mode_order(order)`  
  既存のモード一覧と並び順の変更。

## モード追加の手順

モード追加は `OledModeManager` 内にレンダラを追加し、登録する形がシンプルです。

```python
class OledModeManager:
    def _render_custom(self, now_ms, motor_cmd, motor_cmd_ms, motor_deadman_ms):
        self._oled.show_text("CUSTOM")

    def _register_defaults(self) -> None:
        self.register_mode("custom", self._render_custom)
        self.set_mode_order([OLED_MODE_WELCOME, "custom", OLED_MODE_DRIVE, OLED_MODE_SETTINGS, OLED_MODE_LEGACY])
```

簡易テンプレートを使う場合は以下のように登録できます。

```python
oled_manager.register_template_mode("custom")
```

`renderer` では `self._oled.show_text()` や `render_text_overlay()` を使って描画します。  
新しい assets を使う場合は `_load_assets()` に読み込み処理を追加してください。

## SW 入力（button loop）

SW1/SW2 の扱いは `src/dmc_ai_mobility/app/robot_node.py` の button loop に実装されています。  
現在は以下の動作です:

- 通常モード中: `SW1` 短押しで次モード、`SW2` 短押しで前モード
- `settings` 中: `SW1` 短押しで次項目、`SW2` 短押しで前項目（循環）
- `settings` 中: `SW1` 長押しで確認表示（`OK?`）に遷移
- 確認表示中: `SW1` で実行、`SW2` でキャンセル（settings に戻る）
- `settings` 中: `SW2` 長押しで直前の非 settings モードへ戻る
- `GIT PULL` / `SHUTDOWN` / `REBOOT` 実行時は OLED に実行ステータス（`... running...` / `... now...`）を一時表示
- `GIT PULL` は完了時に `OK` または失敗理由（`DIRTY` など）を一時表示

settings の「決定」は `OledSettingsActionRunner` が実処理に接続します（`robot_node.py` で呼び出し）。
