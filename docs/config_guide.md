# 設定ガイド

このドキュメントは `config.toml` の主要項目を説明します。詳細な既定値は `config.toml` と `src/dmc_ai_mobility/core/config.py` を参照してください。

## 基本

```toml
robot_id = "rasp-zero-01"
```

`robot_id` は Zenoh キーの `dmc_robo/<robot_id>/...` に使われます。

## [motor]

- `deadman_ms`: 指令が途絶してから停止するまでの猶予（ms）
- `deadband_pw`: パルス幅のデッドバンド（1500±x 内は停止扱い）
- `telemetry_hz`: motor/telemetry の publish 周期

## [imu]

- `publish_hz`: IMU 状態の publish 周期

## [oled]

- `max_hz`: OLED の更新上限（Hz）
- `i2c_port`: I2C ポート（Raspberry Pi のバス番号）
- `i2c_address`: OLED の I2C アドレス（例: 0x3C）
- `width`/`height`: OLED 解像度
- `override_s`: Zenoh 経由の表示を何秒だけ優先表示するか
- `boot_image`/`motor_image`: 通常表示用の画像（`.bin` または画像ファイル）
- `default_mode`: UI モードの既定値（`legacy`/`welcome`/`drive`/`settings`）
- `welcome_frames_dir`: ウェルカムアニメのフレームフォルダ
- `welcome_fps`: ウェルカムアニメの再生 FPS
- `welcome_loop`: ウェルカムアニメのループ有無
- `welcome_on_boot`: 起動時にウェルカムアニメを再生するか
- `mode_switch_frames_dir`: モード切替アニメのフレームフォルダ
- `mode_switch_fps`: モード切替アニメの再生 FPS
- `eyes_frames_dir`: 走行モードの“目”アニメのフレームフォルダ
- `eyes_fps`: “目”アニメの再生 FPS

## [oled_settings]

設定モード選択時に実行するコマンド群です。未設定の場合はデフォルトのスクリプトが使われます。

- `enabled`: 設定アクションを有効化
- `cooldown_s`: 連打を抑止するクールダウン秒数
- `calib_cmd`: キャリブレーション実行コマンド（任意）
- `wifi_cmd`: Wi‑Fi 接続コマンド（任意）
- `wifi_ssid`: `wifi_cmd` が未指定の場合に使う SSID
- `wifi_psk_env`: パスフレーズを読む環境変数名（例: `WIFI_PSK`）
- `git_pull_cmd`: Git 更新コマンド（任意）
- `branch_cmd`: ブランチ切替コマンド（任意）
- `branch_target`: デフォルトのターゲットブランチ名
- `shutdown_cmd`: シャットダウンコマンド（任意）
- `reboot_cmd`: 再起動コマンド（任意）
- `sudo_cmd`: `sudo` を使う場合のコマンド（例: `sudo -n`）

## [camera]

- `enable`: カメラの有効/無効
- `device`: V4L2 デバイス番号（例: 0 => `/dev/video0`）
- `width`/`height`/`fps`: 取得サイズと publish 周期
- `auto_trim`: 要求サイズより大きいフレームが返る場合に右/下をトリムする
- `buffer_size`: 内部バッファサイズ（小さくすると遅延を減らせる場合あり）
- `latest_only`: 最新フレームのみ保持し、遅延を溜めない
- `jpeg_quality`: JPEG エンコード品質（1-100、低いほど軽い）

## [camera_h264]

- `enable`: H.264 配信の有効/無効
- `width`/`height`/`fps`: H.264 の解像度とフレームレート
- `bitrate`: H.264 のビットレート（bps）
- `chunk_bytes`: 送信チャンクサイズ（bytes）
- `rpicam-vid` が必要です（bookworm の rpicam-apps）。旧環境は `libcamera-vid` の場合があります。

## [lidar]

- `enable`: LiDAR の有効/無効
- `port`: シリアルポート（例: `/dev/ttyAMA0`）
- `baudrate`: ボーレート
- `publish_hz`: publish 周期
- `front_window_deg`: 正面角度の集計ウィンドウ（度）
- `front_stat`: 集計方法（`mean` or `min`）

## [zenoh]

- `config_path`: Zenoh 設定ファイルのパス（任意）

## 例

```toml
robot_id = "rasp-zero-01"

[motor]
deadman_ms = 300
telemetry_hz = 10

[imu]
publish_hz = 50

[oled]
max_hz = 10
width = 128
height = 32
override_s = 2.0
# boot_image = "assets/bin/boot.bin"
# motor_image = "assets/bin/motor.bin"
# default_mode = "legacy"
# welcome_frames_dir = "assets/oled/welcome"
# welcome_fps = 10
# welcome_loop = false
# welcome_on_boot = true
# mode_switch_frames_dir = "assets/oled/mode_switch"
# mode_switch_fps = 10
# eyes_frames_dir = "assets/oled/eyes"
# eyes_fps = 10

[oled_settings]
enabled = true
cooldown_s = 1.0
wifi_ssid = "YourSSID"
wifi_psk_env = "WIFI_PSK"
branch_target = "main"

[camera]
enable = true
device = 0
width = 640
height = 480
fps = 10
auto_trim = true
buffer_size = 1
latest_only = true
jpeg_quality = 80

[camera_h264]
enable = false
width = 640
height = 480
fps = 30
bitrate = 2000000
chunk_bytes = 65536
```
