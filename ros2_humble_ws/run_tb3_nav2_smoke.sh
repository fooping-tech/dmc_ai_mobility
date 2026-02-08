#!/usr/bin/env bash
set -euo pipefail
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u
export TURTLEBOT3_MODEL=burger

(timeout 240 ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py >/tmp/tb3_world.log 2>&1) &
SIM_PID=$!
sleep 30
(timeout 240 ros2 launch turtlebot3_navigation2 navigation2.launch.py use_sim_time:=True map:=$(ros2 pkg prefix turtlebot3_navigation2)/share/turtlebot3_navigation2/map/map.yaml >/tmp/tb3_nav2.log 2>&1) &
NAV_PID=$!
sleep 25

if ros2 action list | grep -q '/navigate_to_pose'; then
  echo NAV2_ACTION_OK
else
  echo NAV2_ACTION_MISSING
fi
set +e
timeout 30 ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: map}, pose: {position: {x: 0.5, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}" --feedback > /tmp/tb3_goal.log 2>&1
RC=$?
set -e
echo GOAL_CMD_RC=$RC
sed -n '1,120p' /tmp/tb3_goal.log || true
kill $NAV_PID >/dev/null 2>&1 || true
kill $SIM_PID >/dev/null 2>&1 || true
