#!/usr/bin/env bash
set -euo pipefail

MAP_PATH=${1:-/work/maps/map.yaml}
LOG_DIR=${LOG_DIR:-/tmp/dmc_nav2_realrobot_loc}
mkdir -p "$LOG_DIR"

cd /work
source /opt/ros/humble/setup.bash
source /work/install/setup.bash

cleanup() {
  echo "[bringup-loc] stopping launched processes..."
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ros2 launch dmc_nav_bridge bridge_odom.launch.py >"$LOG_DIR/bridge.log" 2>&1 &
ros2 launch dmc_nav_bridge localization.launch.py >"$LOG_DIR/localization.log" 2>&1 &
ros2 launch dmc_nav_bridge nav2_localization.launch.py map:="$MAP_PATH" >"$LOG_DIR/nav2_localization.log" 2>&1 &

echo "[bringup-loc] waiting for topics/actions..."
sleep 10

check_once() {
  local label="$1"
  local cmd="$2"
  set +e
  timeout 8 bash -lc "$cmd" >/dev/null 2>&1
  local rc=$?
  set -e
  if [ $rc -eq 0 ]; then
    echo "[ok] $label"
  else
    echo "[ng] $label"
  fi
}

check_once "/scan" "ros2 topic echo /scan --once"
check_once "/odom_filtered" "ros2 topic echo /odom_filtered --once"
check_once "nav action /navigate_to_pose" "ros2 action list | grep -q /navigate_to_pose"

echo
echo "[bringup-loc] running with map=$MAP_PATH"
echo "[bringup-loc] logs: $LOG_DIR"
echo "[bringup-loc] Ctrl+C to stop all launched processes"
wait
