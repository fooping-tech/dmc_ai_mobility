# RUNBOOK: Real Robot Nav2 Troubleshooting

対象: 実機で `bringup_realrobot_slam.sh` / `bringup_realrobot_localization.sh` 実行時の一次切り分け。

---

## 0) 最初に実行（共通）
```bash
/work/preflight_check.sh
```

失敗した項目に応じて以下へ。

---

## A. `/scan` が来ない

### 症状
- `preflight_check.sh` で `/scan topic` が `[ng]`
- Nav2のcostmap関連が更新されない / 経路が作れない

### 確認コマンド
```bash
ros2 topic list | grep scan
ros2 topic echo /scan --once
ros2 node list | grep zenoh_lidar_bridge
```

### 見るログ
- `/tmp/dmc_nav2_realrobot/bridge.log`
- `/tmp/dmc_nav2_realrobot_loc/bridge.log`

### よくある原因
- `ROBOT_ID` が実機と不一致
- `ZENOH_CONFIG` の接続先不一致
- LiDAR側のzenohキー未配信

### 対応
1. `echo $ROBOT_ID` / `echo $ZENOH_CONFIG` を確認
2. bringup再実行
```bash
export ROBOT_ID=rasp-zero-01
export ZENOH_CONFIG=/work/../zenoh_remote.json5
/work/bringup_realrobot_slam.sh
```
3. bridge.logに `zenoh_lidar_bridge` のエラーがないか確認

---

## B. TF欠落（`odom -> base_link` / `base_link -> base_scan`）

### 症状
- `preflight_check.sh` で TF が `[ng]`
- `Goal was rejected` / `Invalid frame ID` が出る

### 確認コマンド
```bash
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link base_scan
ros2 topic echo /tf --once
```

### 見るログ
- `/tmp/dmc_nav2_realrobot/bridge.log`
- `/tmp/dmc_nav2_realrobot/localization.log`

### よくある原因
- odom bridge停止
- ekf未起動
- launchの途中失敗

### 対応
1. `bridge_odom.launch.py` が起動しているか確認
2. `localization.launch.py` が起動しているか確認
3. bringupを再起動

---

## C. Goal reject / 経路生成失敗

### 症状
- `send_goal.sh` 実行で reject
- `ComputePathToPose` が ABORTED or poses=0

### 確認コマンド
```bash
ros2 action list | grep navigate_to_pose
ros2 topic echo /odom_filtered --once
ros2 topic echo /scan --once
```

### 見るログ
- `/tmp/dmc_nav2_realrobot/nav2_slam.log`
- `/tmp/dmc_nav2_realrobot_loc/nav2_localization.log`

### よくある原因
- ローカライゼーション未収束
- コストマップ更新なし（scan未着）
- map/odom/base系のframe不整合

### 対応
1. localizationが安定するまで少し待つ
2. `/scan` と `/odom_filtered` 再確認
3. 近距離goal（例: 0.3m前方）で再試行
4. 失敗ログ保存して再起動

---

## D. 最短復旧手順（再起動）
```bash
# 既存bringupを止める（実行中のターミナルでCtrl+C）

export ROBOT_ID=rasp-zero-01
export ZENOH_CONFIG=/work/../zenoh_remote.json5
/work/bringup_realrobot_localization.sh /work/maps/map.yaml
/work/preflight_check.sh
/work/send_goal.sh 0.3 0.0 0.0
```

---

## E. 取得しておくべき証跡
- `/tmp/dmc_nav2_realrobot/*.log` もしくは `/tmp/dmc_nav2_realrobot_loc/*.log`
- `preflight_check.sh` の結果
- 失敗した `send_goal.sh` の出力
