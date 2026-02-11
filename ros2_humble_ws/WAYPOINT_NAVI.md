# Waypoint Navigation (任意ウェイポイント指定)

`waypoint_navi.py` は Nav2 の `/navigate_to_pose` に順番にゴールを送る簡易ランナーです。

## 1) 前提
- Localization が起動済み（`/map`, `/scan`, `/navigate_to_pose` がある）
- コンテナ内 `/work` で実行

```bash
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u
```

## 2) 使い方

### A. その場で指定
```bash
python /work/waypoint_navi.py \
  --waypoints "-0.5,2.6,0.0;-0.2,2.2,-1.57;0.0,2.0,3.14"
```

### B. JSONファイル指定（推奨）
```bash
python /work/waypoint_navi.py --file /work/waypoints.sample.json
```

### C. 初期姿勢も自動投入
```bash
python /work/waypoint_navi.py \
  --file /work/waypoints.sample.json \
  --set-initial-pose
```

またはCLIで初期姿勢を直接指定:
```bash
python /work/waypoint_navi.py \
  --waypoints "0.2,0.0,0.0;0.5,0.0,0.0" \
  --set-initial-pose \
  --initial-pose "0.0,0.0,0.0"
```

## 3) 入力フォーマット

- yaw は **radian**（例: `pi/2` は `1.57`）
- JSONは以下形式

```json
{
  "initial_pose": [x, y, yaw],
  "waypoints": [
    [x1, y1, yaw1],
    [x2, y2, yaw2]
  ]
}
```

## 4) よくある注意
- 地図と自己位置がズレているとゴール失敗しやすい
  - 先に RViz の `2D Pose Estimate` で合わせる
- `goal rejected` が出るとき
  - `/navigate_to_pose` のサーバ起動状況を確認
  - コストマップと障害物状況を確認
