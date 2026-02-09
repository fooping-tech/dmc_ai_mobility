# NAV2_REPRO_GUIDE.md

最終更新: 2026-02-09
対象: Raspberry Pi (arm64) / Debian系ホスト / `dmc_ai_mobility`

---

## 0. 前提

- リポジトリ: `/home/fukuhala/python_ws/dmc_ai_mobility`
- Docker利用可能
- ブランチ: `feature/motor-trim-4points`

---

## 1. ROS2 Humble + Nav2 コンテナ環境の作成

```bash
cd /home/fukuhala/python_ws/dmc_ai_mobility
bash scripts/bootstrap_ros2_humble_nav2_docker.sh
```

イメージ作成 + コンテナ起動:

```bash
bash /home/fukuhala/python_ws/dmc_ai_mobility/ros2_humble_ws/run_nav2_container.sh
```

> 以降はコンテナ内で作業。

---

## 2. ワークスペースのビルド

```bash
cd /work
source /opt/ros/humble/setup.bash
python3 -m pip install eclipse-zenoh
colcon build --symlink-install
source install/setup.bash
```

---

## 3. 実機向け基本起動（Bridge + Odom + Lidar + EKF + Nav2）

### 端末A
```bash
/work/start_bridge.sh
```

### 端末B
```bash
/work/start_localization.sh
```

### 端末C（SLAMモード）
```bash
/work/start_nav2_slam.sh
```

### 端末C（保存地図でLocalizationモード）
```bash
/work/start_nav2_localization.sh
```

---

## 4. 地図保存

```bash
/work/save_map.sh map
# => /work/maps/map.yaml が作成される
```

---

## 5. ゴール送信

```bash
/work/send_goal.sh 1.0 0.0 0
# x=1.0m, y=0.0m, yaw=0deg
```

---

## 6. 状態確認コマンド

```bash
ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 topic echo /odom_filtered --once
ros2 action list | grep navigate
ros2 node list
```

TF確認:

```bash
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link base_scan
```

---

## 7. シミュレーション再現（今回の検証用）

今回「Goal rejected」を解消して `SUCCEEDED` に到達した最小条件は、
**TFチェーン + /scan 入力を満たすこと**。

以下はコンテナ内ワンショット例（検証用）:

```bash
source /opt/ros/humble/setup.bash
MAP=/opt/ros/humble/share/nav2_bringup/maps/turtlebot3_world.yaml

# 1) Nav2起動
ros2 launch nav2_bringup bringup_launch.py slam:=False map:=$MAP use_sim_time:=False autostart:=True
```

別端末で:

```bash
source /opt/ros/humble/setup.bash

# 2) TFチェーン
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 odom base_link
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link laser

# 3) /scan投入
ros2 topic pub /scan sensor_msgs/msg/LaserScan \
'{header: {frame_id: laser}, angle_min: -3.14, angle_max: 3.14, angle_increment: 0.01745, time_increment: 0.0, scan_time: 0.1, range_min: 0.05, range_max: 10.0, ranges: [2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0]}' -r 10

# 4) ゴール送信
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
"{pose: {header: {frame_id: map}, pose: {position: {x: 0.2, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"
```

成功時の典型ログ:
- `Goal accepted with ID: ...`
- `Goal finished with status: SUCCEEDED`

---

## 8. 失敗時チェックリスト

### A. `Goal was rejected`
- `ros2 action list` で `/navigate_to_pose` が存在するか
- TFが足りているか（最低 `map->odom->base_link->laser`）
- `/scan` が来ているか

### B. `Timed out waiting for transform ... base_link to odom`
- `odom` フレーム未提供。`map->odom`, `odom->base_link` を確認。

### C. `exec format error`（Docker build時）
- arm64向けROSベースイメージを使用する。

### D. `gzserver` / `gazebo_ros` not found
- Classic Gazebo依存不足。今回の再現は ros_gz 依存確認 + Nav2単体検証で実施。

---

## 9. 追加した主要ファイル

- `scripts/bootstrap_ros2_humble_nav2_docker.sh`
- `ros2_humble_ws/Dockerfile`
- `ros2_humble_ws/run_nav2_container.sh`
- `ros2_humble_ws/start_bridge.sh`
- `ros2_humble_ws/start_localization.sh`
- `ros2_humble_ws/start_nav2_slam.sh`
- `ros2_humble_ws/start_nav2_localization.sh`
- `ros2_humble_ws/send_goal.sh`
- `ros2_humble_ws/save_map.sh`
- `ros2_humble_ws/src/dmc_nav_bridge/...`

---

必要なら次版で「完全自動化スクリプト（1コマンド起動）」を追加できます。
