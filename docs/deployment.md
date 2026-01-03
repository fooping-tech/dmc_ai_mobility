# デプロイ手順（Raspberry Pi）

このドキュメントは systemd で常駐させる手順の要点をまとめたものです。

## 1) 配備

```bash
APP_DIR=/home/fooping/dmc_ai_mobility
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR"
cd "$APP_DIR"
```

## 2) venv 作成

```bash
python3 -m venv /home/fooping/env
/home/fooping/env/bin/pip install -r requirements.txt
```

## 3) 依存パッケージ（H.264 配信を使う場合）

```bash
sudo apt-get update
sudo apt-get install -y rpicam-apps
```

補足:
- Debian bookworm は `rpicam-vid`（rpicam-apps）を使用します。
- 旧環境では `libcamera-vid`（libcamera-apps）を使う場合があります。

## 4) systemd 登録

```bash
sudo cp systemd/dmc-ai-mobility.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmc-ai-mobility.service
```

H.264 の検証で libcamerify を無効化したい場合は、検証用ユニットを使います。

```bash
sudo cp systemd/dmc-ai-mobility-h264.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmc-ai-mobility-h264.service
```

## 5) 動作確認

```bash
sudo systemctl status dmc-ai-mobility.service
journalctl -u dmc-ai-mobility.service -f
```

ログの追従は `journalctl -u dmc-ai-mobility.service -f` で確認できます。

## 6) 設定変更時

`config.toml` を変更したら再起動します。

```bash
sudo systemctl restart dmc-ai-mobility.service
```

## 7) Git 更新と安全な再起動

リモート更新がある場合のみ `git pull --ff-only` を行い、稼働中のサービスを安全に再起動します。

```bash
sudo ./scripts/pull_and_restart.sh
```

補足:
- 作業ツリーが汚れている場合は中断します（必要なら `ALLOW_DIRTY=1`）。
- Fast-forward できない履歴は中断します。
- サービスが停止中の場合は再起動をスキップします。

## 補足

- systemd は `scripts/run_robot.sh` を起動します（`libcamerify` 自動対応）。
- `scripts/run_robot.sh` は `libcamerify` があれば自動使用します（無効化: `DMC_USE_LIBCAMERIFY=0`）。
- `config.toml` は `/home/fooping/dmc_ai_mobility/config.toml` を想定しています。
- venv のパスを変える場合は `systemd/dmc-ai-mobility.service` の `VIRTUAL_ENV` と `PATH` を合わせて変更してください。
