# デバッグ用機能メモ

このドキュメントは、開発・デバッグ時に役立つ「ログ出力／購読ツール」の使い方をまとめたものです。

## robot node: 受信コマンドをターミナルに表示

`motor/cmd` と `oled/cmd` を Zenoh 経由で受信したときに、内容をターミナル（ログ）へ表示できます。

### 間引きあり（デフォルト）

高頻度のコマンドでもログが流れすぎないように、motor は最大 10Hz で間引きます。

    PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --log-level INFO

### 全て表示（注意: とても流れます）

`--log-all-cmd` を付けると、受信した motor/oled コマンドを全てログ表示します。

    PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --log-all-cmd --log-level INFO

## robot node: pigpio に渡すパルス幅（pw_l/pw_r）を常時表示（実機向け）

`PigpioMotorDriver` が `set_servo_pulsewidth()` に渡している `pw_l/pw_r` を標準出力へ `print()` します。

注意:
- 出力は非常に多くなります（motor コマンド送信 Hz に比例）。
- `--dry-run` の場合は mock モータなので表示されません。
- 実機で `pigpiod` が動いている必要があります。

    PYTHONPATH=src python3 -m dmc_ai_mobility.app.cli robot --config ./config.toml --print-motor-pw

### デッドバンド（微小指令の抑制）

`config.toml` の `[motor].deadband_pw` を 0 より大きくすると、両輪のパルス幅が `1500±deadband_pw` に入ったときに左右とも停止扱い（pulsewidth=0）になります。

    [motor]
    deadband_pw = 30

## LiDAR を有効化して publish する（robot node）

LiDAR は `config.toml` の `[lidar]` で有効/無効を切り替えます（既定は無効）。

    [lidar]
    enable = true

publish 先キーと payload は `doc/keys_and_payloads.md` の `### lidar` を参照してください。

## 別PCから subscribe/publish（remote tool）

`examples/remote_zenoh_tool.py` を使った手順は `doc/remote_pubsub/zenoh_remote_pubsub.md` を参照してください。

例:

    # LiDAR: 正面サマリ（JSON）
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 lidar

    # LiDAR: 角度ごとの生値（点群）を表示
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 lidar --scan --print-points --max-points 200
