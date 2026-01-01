# dmc_ai_mobility

![top](assets/image.png)

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

## 構成図
- [ソフト構造](software_structure.md)

## リポジトリ
- [GitHub: fooping-tech/dmc_ai_mobility](https://github.com/fooping-tech/dmc_ai_mobility)

## 関連リポジトリ
- [dmc_ai_host](https://github.com/fooping-tech/dmc_ai_host): Zenoh 経由の遠隔操作 UI/最小ツール。キーボード操作、IMUチャート、カメラ表示、LiDAR 2D 表示、OLED テキスト送信を提供。
- [lerobot_dmc](https://github.com/fooping-tech/lerobot_dmc): LeRobot 連携用プラグイン（dmc_robo 対応）。teleop/record から Zenoh 経由でロボット I/O を扱える。

## 運用・ガイド
- [設定ガイド](config_guide.md)
- [デプロイ手順](deployment.md)
- [デバッグ診断](debugging.md)
- [Zenoh 運用](zenoh_operations.md)
