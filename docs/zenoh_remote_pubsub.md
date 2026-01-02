# 別PCから Zenoh を Subscribe / Publish する方法

このドキュメントは、別のPC（開発PCなど）から Zenoh 経由で本リポジトリのロボットノードに対して Subscribe / Publish を行う方法をまとめたものです。

本リポジトリの Zenoh キー命名規則は `dmc_robo/<robot_id>/<component>/<direction>` です（例: `dmc_robo/rasp-zero-01/motor/cmd`）。

## 前提

- 別PCに Python 3.9+ が入っている
- 別PCからロボット側ネットワークに到達できる（同一LAN等）
- Zenoh の Python 実装（`eclipse-zenoh`）を利用する

インストール:

    python3 -m pip install eclipse-zenoh

最小操作スクリプト:

- `examples/remote_zenoh_tool.py`（このリポジトリに同梱）
  - `motor/stop/oled/imu/camera/lidar` のサブコマンドを提供します

## ネットワーク構成（おすすめ）

複数マシンで確実に見通すには「Zenoh Router」を1台立て、全ノードをそこへ接続する構成がおすすめです。

- Router: どこか1台（例: ロボット側 or ルータ用PC）
- Robot node: `dmc_ai_mobility`（Publish/Subscribe）
- Remote PC: このドキュメントの Python スクリプト（Publish/Subscribe）

注意:
- Router の起動方法は環境で異なります（Rust版 `zenohd` など）。Router を使わない peer 構成でも動きますが、ネットワーク越しの探索が不安定になりやすいです。

## ルータに接続する設定ファイル例（remote側）

別PCに `zenoh_remote.json5` を作成し、`<ROUTER_IP>` を実際のIPに置き換えてください。

    {
      mode: "peer",
      connect: {
        endpoints: ["tcp/<ROUTER_IP>:7447"]
      }
    }

以降の例ではこの `zenoh_remote.json5` を使います。

テンプレート:

- `doc/remote_pubsub/zenoh_remote.json5.example`

### もっと簡単にする方法（おすすめ）

設定ファイルを作らずに、`--connect` で接続先を指定できます（`examples/remote_zenoh_tool.py`）。

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --connect "tcp/<ROUTER_IP>:7447" imu

また、環境変数 `ZENOH_CONFIG` に json5 ファイルパスを設定しておけば、`--zenoh-config` を省略できます（eclipse-zenoh 標準）。

    export ZENOH_CONFIG=/path/to/zenoh_remote.json5
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 imu

## 共通: セッションを開く最小コード

    import zenoh
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    session = zenoh.open(cfg)

## 1) motor を Publish（ロボットを動かす）

ロボットが subscribe しているキー:
- `dmc_robo/<robot_id>/motor/cmd`

payload（JSON）例:
- `v_l` / `v_r`: 左右速度
- `unit`: `"mps"`（本リポジトリの実装は unit は現状ログ用途で、速度解釈はドライバ依存です）
- `deadman_ms`: 途絶時に停止するまでの猶予（ms）

	実行例（`robot_id=rasp-zero-01`）:

	    # (推奨) 付属の最小ツール
	    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 motor --v-l 1.0 --v-r 1.0 --duration-s 1

    python3 - <<'PY'
    import json, time
    import zenoh
    
    robot_id = "rasp-zero-01"
    key = f"dmc_robo/{robot_id}/motor/cmd"
    
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    s = zenoh.open(cfg)
    pub = s.declare_publisher(key)
    
    seq = 0
    for _ in range(50):
        payload = {
            "v_l": 0.10,
            "v_r": 0.10,
            "unit": "mps",
            "deadman_ms": 300,
            "seq": seq,
            "ts_ms": int(time.time() * 1000),
        }
        pub.put(json.dumps(payload).encode("utf-8"))
        seq += 1
        time.sleep(0.05)
    
    s.close()
    PY

止める（ゼロ指令を数回投げる）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 stop

    python3 - <<'PY'
    import json, time
    import zenoh
    
    robot_id = "rasp-zero-01"
    key = f"dmc_robo/{robot_id}/motor/cmd"
    
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    s = zenoh.open(cfg)
    pub = s.declare_publisher(key)
    
    for i in range(5):
        pub.put(json.dumps({"v_l": 0.0, "v_r": 0.0, "unit": "mps", "deadman_ms": 300, "seq": i}).encode("utf-8"))
        time.sleep(0.05)
    
    s.close()
    PY

## 2) imu を Subscribe（状態を見る）

ロボットが publish しているキー:
- `dmc_robo/<robot_id>/imu/state`

実行例:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 imu

    python3 - <<'PY'
    import zenoh
    
    robot_id = "rasp-zero-01"
    key = f"dmc_robo/{robot_id}/imu/state"
    
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    s = zenoh.open(cfg)
    
    def on_sample(sample):
        payload = sample.payload.to_bytes()
        print(payload.decode("utf-8"))
    
    sub = s.declare_subscriber(key, on_sample)
    input("subscribing... press Enter to quit\n")
    sub.undeclare()
    s.close()
    PY

## 3) oled を Publish（表示を変える）

ロボットが subscribe しているキー:
- `dmc_robo/<robot_id>/oled/cmd`

実行例:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 oled --text "Hello from remote"

    python3 - <<'PY'
    import json, time
    import zenoh
    
    robot_id = "rasp-zero-01"
    key = f"dmc_robo/{robot_id}/oled/cmd"
    
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    s = zenoh.open(cfg)
    pub = s.declare_publisher(key)
    
    pub.put(json.dumps({"text": "Hello from remote", "ts_ms": int(time.time() * 1000)}).encode("utf-8"))
    time.sleep(0.2)
    
    s.close()
    PY

## 3b) oled 画像（mono1 bytes）を Publish（一定時間だけ表示）

ロボットが subscribe しているキー:
- `dmc_robo/<robot_id>/oled/image/mono1`

この payload は SSD1306 の mono1 バッファ（生 bytes）です。サイズは `width * height / 8` bytes で、ロボット側の `config.toml` の `[oled].width`/`[oled].height` に一致する必要があります。

実行例（入力画像を変換して送信）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 oled-image \
      --image ./docs/assets/logo.png --width 128 --height 32

実行例（事前に生成した .bin を送信）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 oled-image \
      --bin ./assets/oled/boot.bin --width 128 --height 32

## 4) camera を Subscribe（JPEG と meta）

ロボットが publish しているキー:
- JPEG: `dmc_robo/<robot_id>/camera/image/jpeg`
- meta: `dmc_robo/<robot_id>/camera/meta`

JPEG は bytes のまま届くので、ファイルに保存できます。

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera --out-dir ./camera_frames --print-meta

    python3 - <<'PY'
    import json
    import zenoh
    
    robot_id = "rasp-zero-01"
    key_img = f"dmc_robo/{robot_id}/camera/image/jpeg"
    key_meta = f"dmc_robo/{robot_id}/camera/meta"
    
    cfg = zenoh.Config.from_file("zenoh_remote.json5")
    s = zenoh.open(cfg)
    
    state = {"seq": None}
    
    def on_meta(sample):
        meta = json.loads(sample.payload.to_bytes().decode("utf-8"))
        state["seq"] = meta.get("seq")
        print("meta:", meta)
    
    def on_img(sample):
        jpg = sample.payload.to_bytes()
        seq = state["seq"]
        name = f"frame_{seq if seq is not None else 'unknown'}.jpg"
        with open(name, "wb") as f:
            f.write(jpg)
        print("saved:", name, len(jpg), "bytes")
    
    sub_meta = s.declare_subscriber(key_meta, on_meta)
    sub_img = s.declare_subscriber(key_img, on_img)
    input("subscribing... press Enter to quit\n")
    sub_img.undeclare()
    sub_meta.undeclare()
    s.close()
    PY

## 4b) camera レイテンシ計測（グラフ表示）

`camera/meta` の `capture_ts_ms` と受信時刻から end-to-end レイテンシを計測します。  
`--plot` または `--plot-out` を使う場合は `matplotlib` が必要です（`pip install matplotlib`）。

計測の意味（camera-latency の表示項目。グラフは read_ms + pipeline_ms + publish_to_remote_ms を積み上げ表示）:
- `read_ms`: `cap.read()` の開始→終了（キャプチャ読み取り時間の近似）。
- `pipeline_ms`: キャプチャ終了→publish（JPEG encode + publish を含む）。
- `start_to_publish_ms`: キャプチャ開始→publish（`read_ms + pipeline_ms`）。
- `publish_to_remote_ms`（remote tool）: publish→受信（時計同期が必要）。
- キャプチャ開始→publish を見たい場合は `publish_mono_ms - capture_start_mono_ms` を使います。

実行例（コンソール表示のみ）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-latency \
      --duration-s 20 --print-each

実行例（PNG 出力）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-latency \
      --duration-s 30 --plot-out ./camera_latency.png

実行例（画面表示 + 保存）:

    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-latency \
      --duration-s 30 --plot --plot-out ./camera_latency.png

## 5) lidar を Subscribe（角度ごとの生値 / 正面サマリ）

ロボットが publish しているキー:

- scan（角度ごとの生値）: `dmc_robo/<robot_id>/lidar/scan`
- front（正面サマリ）: `dmc_robo/<robot_id>/lidar/front`

payload の詳細は `doc/keys_and_payloads.md` の `### lidar` を参照してください。

実行例:

    # (デフォルト) lidar/front を subscribe して JSON を表示
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 lidar

    # lidar/scan の JSON をそのまま表示（点群配列が大きいので注意）
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 lidar --scan --print-json

    # lidar/scan を角度(deg)/距離(m)として表示（先頭 N 点のみ）
    python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 lidar --scan --print-points --max-points 200

## トラブルシュート

- Remote から何も届かない:
  - `robot_id` が一致しているか確認（`config.toml` の `robot_id` と同じにする）
  - Router を使う構成なら、remote も robot も同じ router に `connect/endpoints` で接続しているか確認
- カメラが取れない（Raspberry Pi / libcamera 環境）:
  - ロボット側起動は `libcamerify` が必要なことがあります（`scripts/run_robot.sh` は自動対応済み）
