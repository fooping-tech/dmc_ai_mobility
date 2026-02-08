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

## 4) Start SLAM + Nav2 (new terminal in same container)
```bash
/work/start_nav2_slam.sh
```

## 5) Check topics/TF
```bash
ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link base_scan
```

## 6) Send goal
```bash
/work/send_goal.sh 1.0 0.0 0
```

Notes:
- `/scan` must be published for costmaps/Nav2.
- Current odom is wheel-command integration from telemetry; for production accuracy, replace with encoder/IMU fused odom (robot_localization).
