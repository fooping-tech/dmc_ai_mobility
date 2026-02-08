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

## 3) Start bridge + odom
```bash
ros2 launch dmc_nav_bridge bridge_odom.launch.py
```

## 4) Start SLAM + Nav2 (new terminal in same container)
```bash
cd /work
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch dmc_nav_bridge nav2_slam.launch.py
```

## 5) Send goal
```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
"{pose: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"
```

Notes:
- `/scan` must be published for costmaps/Nav2.
- Current odom is wheel-command integration from telemetry; for production accuracy, replace with encoder/IMU fused odom (robot_localization).
