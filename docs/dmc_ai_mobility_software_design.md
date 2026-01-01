# ソフト設計書  
**DMC_AI_MOBILITY – AIロボット制御ソフトウェア**

---

## 1. 目的・概要

本ソフトウェアは、Raspberry Pi Zero 上で動作する **AIロボット制御用 Python ソフトウェア**である。  
Zenoh を通信基盤として、以下の機能を実装する。

- Zenoh 経由で左右モータ指示値を受信し、ロボットを走行制御する  
- Zenoh 経由で IMU センサ値を配信する  
- Zenoh 経由で OLED 表示内容（テキスト/画像）を受信し、表示を更新する  
- Zenoh 経由で Camera 画像を配信する  
- Zenoh 経由で LiDAR 点群と正面距離サマリを配信する  
- 健康状態（稼働時間）のハートビートを配信する  
- 本番常駐運用を前提とし、将来的な **多機体・多ノード構成**に耐える設計とする  

---

## 2. システム全体構成

### 2.1 実行環境

- OS: Raspberry Pi OS (Linux)
- 言語: Python 3.x
- 通信ミドルウェア: Zenoh
- 実行形態: systemd による常駐サービス

### 2.2 接続デバイス

| デバイス | 接続方式 |
|--------|--------|
| モータ | GPIO / PWM / I2C / UART |
| IMU | I2C / SPI |
| OLED | I2C |
| Camera | libcamera + libcamerify（V4L2互換） |
| LiDAR | UART |

---

## 3. ディレクトリ構成設計

```text
dmc_ai_mobility/
  pyproject.toml
  README.md
  config.toml

  configs/
    imu_config.json
    motor_config.json
    zenoh.json5

  src/
    dmc_ai_mobility/
      app/
        robot_node.py
        health_node.py
      drivers/
        motor.py
        imu.py
        oled.py
        camera_v4l2.py
        lidar.py
        ydlidar.py
        _ydlidar.so
      zenoh/
        session.py
        keys.py
        pubsub.py
      core/
        config.py
        timing.py
        oled_bitmap.py

  scripts/
    run_robot.sh
  systemd/
    dmc-ai-mobility.service
```

---

## 4. Zenoh 通信設計

### 4.1 キー命名規則

```
dmc_robo/<robot_id>/<component>/<direction>
```

---

### 4.2 通信一覧

#### モータ指示値（Subscribe）

- Key: `dmc_robo/<robot_id>/motor/cmd`

```json
{
  "v_l": 0.10,
  "v_r": 0.12,
  "unit": "mps",
  "deadman_ms": 300,
  "seq": 184,
  "ts_ms": 1735467890123
}
```

#### モータテレメトリ（Publish）

- Key: `dmc_robo/<robot_id>/motor/telemetry`

#### IMU 状態（Publish）

- Key: `dmc_robo/<robot_id>/imu/state`

#### OLED 表示（Subscribe）

- Key: `dmc_robo/<robot_id>/oled/cmd`
- Key: `dmc_robo/<robot_id>/oled/image/mono1`

`oled/cmd` は JSON でテキスト表示、`oled/image/mono1` は SSD1306 の mono1 バッファ（生 bytes）を受け取る。  
受信した表示は一定時間（`config.toml` の `[oled].override_s`）だけ表示し、その後は通常表示へ戻す。

#### Camera 画像（Publish）

- JPEG: `dmc_robo/<robot_id>/camera/image/jpeg`
- Meta: `dmc_robo/<robot_id>/camera/meta`

#### LiDAR（Publish）

- Scan: `dmc_robo/<robot_id>/lidar/scan`
- Front summary: `dmc_robo/<robot_id>/lidar/front`

#### Health（Publish）

- Key: `dmc_robo/<robot_id>/health/state`

---

## 5. Camera 設計（libcamerify 前提）

- libcamerify により V4L2 デバイスとして取得
- OpenCV（cv2.VideoCapture）を使用
- JPEG エンコード後 Zenoh で Publish

---

## 6. 本番ノード設計

### robot_node.py の責務

- Zenoh セッション管理
- motor / oled Subscribe（oled は text + mono1）
- motor telemetry Publish
- imu / camera / lidar Publish
- deadman による安全停止
- camera 障害の局所化
- OLED の表示優先度制御（通常表示 vs 一時上書き）

### health_node.py の責務

- `health/state` を 1Hz で Publish（稼働時間と時刻）

---

## 7. 制御周期例

| 機能 | 周期 |
|----|----|
| Motor | イベント駆動 |
| Motor telemetry | 10Hz（設定可） |
| IMU | 50Hz |
| OLED | 最大10Hz |
| Camera | 5–10Hz |
| LiDAR | 10Hz（設定可） |
| Health | 1Hz |

---

## 8. 設定ファイル例

```toml
robot_id = "rasp-zero-01"

[motor]
deadman_ms = 300
telemetry_hz = 10

[imu]
publish_hz = 50

[oled]
max_hz = 10
i2c_port = 1
i2c_address = 0x3C
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

[lidar]
enable = false
port = "/dev/ttyAMA0"
baudrate = 230400
publish_hz = 10
front_window_deg = 10
front_stat = "mean"

[zenoh]
# config_path = "configs/zenoh.json5"
```

---

## 9. 安全・運用設計

- motor 指示途絶時は即停止
- Zenoh 切断時はモータ停止
- camera はベストエフォート
- OLED 受信は一時表示に留め、通常表示に復帰する

---

## 10. 結論

本設計は本番常駐運用を前提とした、拡張性・安全性重視の構成である。  
そのまま実装に着手可能である。
