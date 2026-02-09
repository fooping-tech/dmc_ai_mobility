#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

docker build -t dmc-ros2-humble-nav2 -f "$ROOT/Dockerfile" "$ROOT"

docker run --rm -it \
  --net=host \
  --privileged \
  -e DISPLAY=${DISPLAY:-} \
  -e TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL:-burger} \
  -e AUTO_ROBOT_DESCRIPTION=${AUTO_ROBOT_DESCRIPTION:-1} \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$(cd "$ROOT/.." && pwd)":/repo \
  -v "$ROOT":/work \
  dmc-ros2-humble-nav2 \
  bash -lc 'set +u; source /opt/ros/humble/setup.bash; set -u; if [ "${AUTO_ROBOT_DESCRIPTION}" = "1" ]; then ros2 launch turtlebot3_description robot_state_publisher.launch.py >/tmp/robot_description.log 2>&1 & echo "[run_nav2_container] robot_state_publisher started (log: /tmp/robot_description.log)"; fi; exec bash'
