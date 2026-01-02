# Zenoh 運用

このドキュメントは Zenoh の基本的な運用と接続設定の要点をまとめたものです。詳細な pub/sub の例は `docs/zenoh_remote_pubsub.md` を参照してください。

## 設定ファイルの使い方

- `zenoh_remote.json5.example` をコピーして `zenoh_remote.json5` を作成します。
- `config.toml` の `[zenoh].config_path` に設定するか、CLI の `--zenoh-config` で指定します。

```bash
cp docs/zenoh_remote.json5.example zenoh_remote.json5
```

## 接続先の上書き

`examples/remote_zenoh_tool.py` は `--connect` で接続先を上書きできます。

```bash
python3 examples/remote_zenoh_tool.py \
  --robot-id rasp-zero-01 \
  --connect "tcp/192.168.1.10:7447" \
  imu
```

## 代表的なキー

- motor cmd: `dmc_robo/<robot_id>/motor/cmd`
- oled cmd: `dmc_robo/<robot_id>/oled/cmd`
- oled image: `dmc_robo/<robot_id>/oled/image/mono1`
- camera jpeg/meta: `dmc_robo/<robot_id>/camera/image/jpeg` / `camera/meta`
- camera h264/meta: `dmc_robo/<robot_id>/camera/video/h264` / `camera/video/h264/meta`
- lidar scan/front: `dmc_robo/<robot_id>/lidar/scan` / `lidar/front`
- health state: `dmc_robo/<robot_id>/health/state`

キーと payload の詳細は `docs/keys_and_payloads.md` を参照してください。
