# SLAM Quickstart (Real Robot)

このページは「実機でSLAMを開始して、地図保存まで行う」ための最短手順です。

前提:
- コンテナは `run_nav2_container.sh` で起動済み
- コンテナ内で `/work` が見えている
- `ROBOT_ID`, `ZENOH_CONFIG` が正しい

---

## 0) 環境読み込み
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

## 1) SLAM起動（推奨: no-EKF）
まずは安定性優先で no-EKF 版。

```bash
/work/bringup_realrobot_slam_noekf.sh
```

EKF版を使う場合:
```bash
/work/bringup_realrobot_slam.sh
```

---

## 2) 別ターミナルで健全性チェック
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

## 3) RVizで確認
```bash
rviz2
```

推奨表示:
- Fixed Frame: `map`
- `Map`
- `TF`
- `LaserScan`（topic: `/scan`）

---

## 4) 地図作成
- 手動でロボットをゆっくり動かして探索
- 未探索領域を減らす

---

## 5) 地図保存
```bash
/work/save_map.sh map
```

保存先例:
- `/work/maps/map.yaml`
- `/work/maps/map.pgm`

---

## 6) Localizationモードで再起動（保存地図使用）
```bash
/work/bringup_realrobot_localization.sh /work/maps/map.yaml
```

---

## 7) Goal送信テスト
```bash
/work/send_goal.sh 0.3 0.0 0.0
```

---

## トラブル時
- `/work/RUNBOOK_REALROBOT_NAV2.md`
- EKFでNaNが出る場合は no-EKF で先に動作確認する
