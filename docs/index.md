# dmc_ai_mobility

Raspberry Pi OS 上で動作する AI ロボット制御用 Python ソフトウェアです。  
Zenoh を通信基盤とし、以下を扱います。

- 左右モータ制御
- IMU センサ配信
- OLED 表示
- カメラ画像配信
- 本番常駐運用（systemd）

## まず読む
- [Software Design](dmc_ai_mobility_software_design.md)
- [Calibration](calibration.md)

## 通信・API
- [Zenoh Keys and Payloads](keys_and_payloads.md)
- [Zenoh Remote Pub/Sub](zenoh_remote_pubsub.md)
