#!/usr/bin/env bash
set -euo pipefail
cd /work
set +u
source /opt/ros/humble/setup.bash
set -u
mkdir -p src

# turtlebot3 sources (Humble)
if [ ! -d src/turtlebot3 ]; then
  git clone --depth 1 -b humble https://github.com/ROBOTIS-GIT/turtlebot3.git src/turtlebot3
fi
if [ ! -d src/turtlebot3_simulations ]; then
  git clone --depth 1 -b humble https://github.com/ROBOTIS-GIT/turtlebot3_simulations.git src/turtlebot3_simulations
fi

rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-up-to turtlebot3_gazebo turtlebot3_navigation2 || colcon build --symlink-install

echo "TB3 source setup done"
