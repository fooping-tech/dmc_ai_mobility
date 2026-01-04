# OLED 設定アクション

OLED の `settings` モードで選択された項目は、`OledSettingsActionRunner` を通じて実処理に接続されます。

## 対応アクション

- `CALIB`: モーターキャリブレーション起動
- `WIFI`: Wi‑Fi 接続
- `GIT PULL`: Git 更新 + 再起動
- `BRANCH`: ブランチ切り替え
- `SHUTDOWN`: シャットダウン
- `REBOOT`: 再起動

## 設定（config.toml）

`[oled_settings]` で各アクションのコマンドや SSID を上書きできます。  
詳細は `docs/config_guide.md` を参照してください。

`cooldown_s` は連打抑止用のクールダウンで、`enabled=false` で無効化できます。

## 既定スクリプト

未指定の場合、以下のスクリプトが使われます。

- Wi‑Fi: `scripts/oled_wifi_connect.sh`
- ブランチ切り替え: `scripts/oled_switch_branch.sh`
- Git 更新: `scripts/pull_and_restart.sh`

`oled_wifi_connect.sh` は `WIFI_SSID`（必須）と `WIFI_PSK`（任意）を参照します。  
`oled_switch_branch.sh` は `TARGET_BRANCH` を要求します（`oled_settings.branch_target` で設定）。
