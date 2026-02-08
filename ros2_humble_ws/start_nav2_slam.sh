#!/usr/bin/env bash
set -euo pipefail
cd /work
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
ros2 launch dmc_nav_bridge nav2_slam.launch.py
