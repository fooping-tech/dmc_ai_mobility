# web_nav2_ui (MVP)

ブラウザで `/map` を表示し、クリックで `NavigateToPose` goal を送るUIです。
Single Goal に加え、Waypoint Add モードで複数点を蓄積して順次実行できます。

## 1) 前提
- Nav2 stackが起動済み
- `/map`, `/odom`, `/navigate_to_pose` が利用可能

## 2) 起動（コンテナ内）
```bash
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

python3 -m pip install -r /work/web_nav2_ui/requirements.txt
python3 -m uvicorn web_nav2_ui.backend.main:app --host 0.0.0.0 --port 8088
```

## 3) ブラウザ
- `http://<raspberrypi-ip>:8088`

## UI操作
- `Single Goal` モード: クリック即送信
- `Waypoint Add` モード: クリックで waypoint を追加
- `Run Waypoints`: 追加順で逐次実行
- `Clear Waypoints`: クリア

## API
- `GET /api/map`
- `GET /api/pose`
- `POST /api/goal` `{x,y,yaw_deg}`
- `POST /api/waypoints/run` `{waypoints:[{x,y,yaw_deg}, ...]}`
- `GET /api/goal/status`
