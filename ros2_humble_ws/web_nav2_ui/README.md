# web_nav2_ui (MVP)

ブラウザで `/map` を表示し、クリックで `NavigateToPose` goal を送る最小UIです。

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

## API
- `GET /api/map`
- `GET /api/pose`
- `POST /api/goal` `{x,y,yaw_deg}`
- `GET /api/goal/status`
