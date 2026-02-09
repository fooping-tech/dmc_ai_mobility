#!/usr/bin/env bash
set -euo pipefail

ROBOT_ID=${ROBOT_ID:-rasp-zero-01}
ZENOH_CONFIG=${ZENOH_CONFIG:-/repo/zenoh_remote.json5}
LOG_DIR=${LOG_DIR:-/tmp/dmc_nav2_realrobot_noekf}
mkdir -p "$LOG_DIR"

cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

cleanup() {
  echo "[bringup-noekf] stopping launched processes..."
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ros2 launch dmc_nav_bridge bridge_odom.launch.py \
  robot_id:="$ROBOT_ID" zenoh_config:="$ZENOH_CONFIG" >"$LOG_DIR/bridge.log" 2>&1 &
B_PID=$!
echo "[bringup-noekf] bridge pid=$B_PID"

ros2 launch dmc_nav_bridge nav2_slam.launch.py >"$LOG_DIR/nav2_slam.log" 2>&1 &
N_PID=$!
echo "[bringup-noekf] nav2_slam pid=$N_PID"

echo "[bringup-noekf] robot_id=$ROBOT_ID zenoh_config=$ZENOH_CONFIG"
echo "[bringup-noekf] waiting for topics/actions..."
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
check_once "/odom" "ros2 topic echo /odom --once"
check_once "tf odom->base_link" "ros2 run tf2_ros tf2_echo odom base_link"
check_once "tf base_link->base_scan" "ros2 run tf2_ros tf2_echo base_link base_scan"
check_once "nav action /navigate_to_pose" "ros2 action list | grep -q /navigate_to_pose"

echo
echo "[bringup-noekf] running. logs: $LOG_DIR"
echo "[bringup-noekf] Ctrl+C to stop all launched processes"
wait
