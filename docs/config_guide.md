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

## [camera]

- `enable`: カメラの有効/無効
- `device`: V4L2 デバイス番号（例: 0 => `/dev/video0`）
- `width`/`height`/`fps`: 取得サイズと publish 周期
- `auto_trim`: 要求サイズより大きいフレームが返る場合に右/下をトリムする
- `buffer_size`: 内部バッファサイズ（小さくすると遅延を減らせる場合あり）
- `latest_only`: 最新フレームのみ保持し、遅延を溜めない

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

[camera]
enable = true
device = 0
width = 640
height = 480
fps = 10
auto_trim = true
buffer_size = 1
latest_only = true
```
