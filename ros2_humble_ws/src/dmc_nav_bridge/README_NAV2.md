# ROS2 Humble + Nav2 quick start (Docker)

## 1) Build and enter container
```bash
bash /work/../ros2_humble_ws/run_nav2_container.sh
```

## 2) Build workspace
```bash
cd /work
source /opt/ros/humble/setup.bash
python3 -m pip install eclipse-zenoh
colcon build --symlink-install
source install/setup.bash
```

## 3) Start bridge + odom + scan bridge
```bash
/work/start_bridge.sh
```

## 4) Start localization EKF (new terminal)
```bash
cd /work
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
ros2 launch dmc_nav_bridge localization.launch.py
```

## 5) Start SLAM + Nav2 (new terminal)
```bash
/work/start_nav2_slam.sh
```

## 6) Check topics/TF
```bash
ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 topic echo /odom_filtered --once
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link base_scan
```

## 7) Send goal
```bash
/work/send_goal.sh 1.0 0.0 0
```

Notes:
- `/scan` must be published for costmaps/Nav2.
- Current odom is wheel-command integration from telemetry; for production accuracy, replace with encoder/IMU fused odom (robot_localization).


## 8) Save map after SLAM
```bash
/work/save_map.sh map
```

## 9) Restart in localization mode (saved map)
```bash
/work/start_bridge.sh
/work/start_localization.sh
/work/start_nav2_localization.sh
```

## 10) One-command bringup for real robot (recommended)
SLAM mode:
```bash
/work/bringup_realrobot_slam.sh
```

SLAM mode (EKFなし / troubleshooting fallback):
```bash
/work/bringup_realrobot_slam_noekf.sh
```

Localization mode (map path optional):
```bash
/work/bringup_realrobot_localization.sh /work/maps/map.yaml
```

Optional env vars:
```bash
export ROBOT_ID=rasp-zero-01
export ZENOH_CONFIG=/work/../zenoh_remote.json5
```

## 11) Preflight check (before sending goals)
```bash
/work/preflight_check.sh
```

Checks:
- `/scan`
- `/odom` and `/odom_filtered`
- `odom -> base_link`
- `base_link -> base_scan`
- `/navigate_to_pose` action availability

Logs:
- SLAM: `/tmp/dmc_nav2_realrobot`
- Localization: `/tmp/dmc_nav2_realrobot_loc`

## 12) Operations docs
- Troubleshooting runbook: `/work/RUNBOOK_REALROBOT_NAV2.md`
- Test-day quick checklist: `/work/TESTDAY_CHECKLIST_10MIN.md`

## 13) Offline parameter benchmark (without real robot)
Run planner/costmap parameter comparison on custom map:
```bash
/work/benchmark_nav2_params.sh
```

Outputs:
- `/work/nav2_param_benchmark.csv`
- `/work/nav2_param_benchmark.md`

Main compared knobs:
- `planner_server.GridBased.use_astar`
- `planner_server.GridBased.tolerance`
- `global/local_costmap.inflation_layer.inflation_radius`
