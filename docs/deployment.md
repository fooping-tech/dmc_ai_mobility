# デプロイ手順（Raspberry Pi）

このドキュメントは systemd で常駐させる手順の要点をまとめたものです。

## 1) 配備

```bash
sudo cp -r . /opt/dmc_ai_mobility
cd /opt/dmc_ai_mobility
```

## 2) systemd 登録

```bash
sudo cp systemd/dmc-ai-mobility.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmc-ai-mobility.service
```

## 3) 動作確認

```bash
sudo systemctl status dmc-ai-mobility.service
journalctl -u dmc-ai-mobility.service -f
```

## 4) 設定変更時

`config.toml` を変更したら再起動します。

```bash
sudo systemctl restart dmc-ai-mobility.service
```

## 5) Git 更新と安全な再起動

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
- `config.toml` は `/opt/dmc_ai_mobility/config.toml` を想定しています。
