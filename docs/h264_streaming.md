# H.264 配信設定マニュアル

Raspberry Pi (bookworm + rpicam-apps) で H.264 を配信し、リモートで表示するための手順です。

## 1) 依存パッケージ

```bash
sudo apt-get update
sudo apt-get install -y rpicam-apps
```

補足:
- bookworm は `rpicam-vid` を使用します。
- 旧環境の場合は `libcamera-vid`（libcamera-apps）になります。

## 2) config.toml

H.264 用の設定を有効化し、JPEG カメラは無効化します。

```toml
[camera]
enable = false

[camera_h264]
enable = true
width = 640
height = 480
fps = 30
bitrate = 2000000
chunk_bytes = 65536
```

## 3) systemd (libcamerify 無効)

H.264 配信は `libcamerify` と競合する場合があるため、検証用ユニットを使います。

```bash
sudo systemctl stop dmc-ai-mobility.service
sudo cp systemd/dmc-ai-mobility-h264.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmc-ai-mobility-h264.service
```

通常ユニットで無効化したい場合は以下でも可:

```bash
sudo systemctl edit dmc-ai-mobility.service
```

```
[Service]
Environment=DMC_USE_LIBCAMERIFY=0
```

## 4) 起動確認

```bash
sudo systemctl status dmc-ai-mobility-h264.service
journalctl -u dmc-ai-mobility-h264.service -f
pgrep -a rpicam-vid
```

ログに `camera h264 started` が出れば起動成功です。

## 5) リモートで表示

リアルタイム表示:

```bash
python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-h264 \
  --play --flush
```

ファイル保存:

```bash
python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-h264 \
  --out ./camera_stream.h264 --flush --print-meta
```

リモート側でエンコードして保存:

```bash
python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-h264 \
  --encode-out ./camera_stream.mp4 --flush
```

生の .h264 を保存しない場合:

```bash
python3 examples/remote_zenoh_tool.py --robot-id rasp-zero-01 --zenoh-config ./zenoh_remote.json5 camera-h264 \
  --no-raw --play --encode-out ./camera_stream.mp4 --flush
```

※ `--encode-out` は `ffmpeg` が必要です。

保存ファイルの再生:

```bash
ffplay -f h264 -fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 ./camera_stream.h264
```

## 6) トラブルシューティング

- `Multiple CameraManager objects are not allowed`
  - 他のカメラプロセス競合や `libcamerify` が原因です。
  - `rpicam-vid` が動いていないか確認し、`DMC_USE_LIBCAMERIFY=0` を設定してください。

- `rpicam-vid exited (code=-6)`
  - 競合または初期化失敗です。上記と同様にプロセス競合と `libcamerify` を確認してください。

- `non-existing PPS` / `no frame`
  - ストリーム途中から再生を開始している状態です。
  - 受信側を先に起動してからロボット側サービスを再起動すると改善します。

- `No accelerated colorspace conversion...`
  - 色変換が CPU になっている警告です。表示できていれば無視して問題ありません。
