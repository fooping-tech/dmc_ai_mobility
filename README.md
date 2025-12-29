# dmc_ai_mobility

Raspberry Pi OS 上で動作する **AI ロボット制御用 Python ソフトウェア**です。通信基盤に Zenoh を使い、以下を行います。

- motor: 速度指令を Subscribe して走行制御（deadman で安全停止）
- imu: IMU 状態を Publish
- oled: 表示コマンドを Subscribe
- camera: JPEG とメタデータを Publish（任意）

設計の概要は `dmc_ai_mobility_software_design.md` を参照してください。

## Quickstart（ハード無し / Zenoh 無し）

開発機で動作確認できる `--dry-run` を用意しています（Zenoh/hardware 依存なし）。

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests

# dry-run 起動（no-camera はログが落ち着くので推奨）
PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot \
  --config ./config.toml \
  --robot-id devbot \
  --dry-run \
  --no-camera \
  --log-level INFO
```

ログ例（順不同）:

- `dry-run subscribed dmc_robo/devbot/motor/cmd`
- `dry-run subscribed dmc_robo/devbot/oled/cmd`
- `deadman timeout -> motor stop`

## CLI

`src/dmc_ai_mobility/app/cli.py` が CLI の入口です。

```bash
# robot node
PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --dry-run

# health node（ハートビート）
PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli health --config ./config.toml --dry-run
```

## 設定（config.toml）

`config.toml` を編集します（例は `config.toml` にあります）。

- `robot_id`: Zenoh キーに含まれるロボット識別子
- `[motor].deadman_ms`: 指令が途絶したら停止するまでの ms
- `[imu].publish_hz`: IMU publish 周期（Hz）
- `[oled].max_hz`: OLED 更新上限（Hz）
- `[camera]`: カメラ設定（enable/device/width/height/fps）
- `[zenoh].config_path`: Zenoh 設定ファイルへのパス（任意）

## Zenoh キー

命名規則:

`dmc_robo/<robot_id>/<component>/<direction>`

主なキー（詳細は `src/dmc_ai_mobility/zenoh/keys.py`）:

- motor cmd（Subscribe）: `dmc_robo/<robot_id>/motor/cmd`
- imu state（Publish）: `dmc_robo/<robot_id>/imu/state`
- oled cmd（Subscribe）: `dmc_robo/<robot_id>/oled/cmd`
- camera jpeg（Publish）: `dmc_robo/<robot_id>/camera/image/jpeg`
- camera meta（Publish）: `dmc_robo/<robot_id>/camera/meta`

motor cmd payload（JSON）例:

```json
{"v_l":0.10,"v_r":0.12,"unit":"mps","deadman_ms":300,"seq":184,"ts_ms":1735467890123}
```

## systemd（Raspberry Pi）

`systemd/dmc-ai-mobility.service` は配備例です。`/opt/dmc_ai_mobility` 配下に配置する想定なので、環境に合わせて `WorkingDirectory` 等を調整してください。

```bash
sudo cp -r . /opt/dmc_ai_mobility
sudo cp systemd/dmc-ai-mobility.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmc-ai-mobility.service
```

## スクリプト

`scripts/run_robot.sh` は `PYTHONPATH` を設定して robot node を起動する簡易ランナーです。

```bash
./scripts/run_robot.sh ./config.toml --dry-run --no-camera --robot-id devbot
```

## 開発メモ

- `src/dmc_ai_mobility/app/robot_node.py` が統合ノード（subscribe/publish/deadman）です。
- 実機ドライバはオプション依存です（例: `pigpio`, `mpu9250_jmdev`, `opencv-python`, `zenoh`）。
- 依存は `pyproject.toml` の optional extras に分けています。
