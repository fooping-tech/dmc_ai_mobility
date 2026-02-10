# SLAM Quickstart (Real Robot)

このページは「実機でSLAMを開始して、地図保存まで行う」ための最短手順です。

前提:
- `ros2_humble_ws` と `/repo` がマウントされたコンテナを使用する
- `ROBOT_ID`, `ZENOH_CONFIG` が正しい

---

## 0) コンテナ起動（ホスト側）
```bash
xhost +SI:localuser:root
cd /home/fukuhala/python_ws/dmc_ai_mobility/ros2_humble_ws
./run_nav2_container.sh
```

補足:
- `xhost +SI:localuser:root` はコンテナ内 root で RViz 表示するために必要
- `run_nav2_container.sh` は `/repo` と `/work` を自動マウントします
- 参考: `/work/src/dmc_nav_bridge/README_NAV2.md`

---

## 1) 環境読み込み（コンテナ内）
```bash
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

export ROBOT_ID=rasp-zero-01
export ZENOH_CONFIG=/repo/zenoh_remote.json5
```

---

## 2) SLAM起動（推奨: no-EKF）
まずは安定性優先で no-EKF 版。

```bash
/work/bringup_realrobot_slam_noekf.sh
```

EKF版を使う場合:
```bash
/work/bringup_realrobot_slam.sh
```

---

## 3) 別ターミナルで健全性チェック
```bash
docker exec -it $(docker ps --filter ancestor=dmc-ros2-humble-nav2 -q | head -n1) bash
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 action list | grep navigate_to_pose
```

最低条件:
- `/scan` が出る
- `/odom` が出る
- `/navigate_to_pose` がある

---

## 4) RVizで確認
```bash
rviz2
```

推奨表示:
- Fixed Frame: `map`
- `Map`
- `TF`
- `LaserScan`（topic: `/scan`）

---

## 5) 地図作成
- 手動でロボットをゆっくり動かして探索
- 未探索領域を減らす

---

## 6) 地図保存
```bash
/work/save_map.sh map
```

保存先例:
- `/work/maps/map.yaml`
- `/work/maps/map.pgm`

---

## 7) Localizationモードで再起動（保存地図使用）
```bash
/work/bringup_realrobot_localization.sh /work/maps/map.yaml
```

---

## 8) Goal送信テスト
```bash
/work/send_goal.sh 0.3 0.0 0.0
```

---

## トラブル時
- `/work/RUNBOOK_REALROBOT_NAV2.md`
- EKFでNaNが出る場合は no-EKF で先に動作確認する
