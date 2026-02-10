#!/usr/bin/env bash
set -euo pipefail

MAP_PATH=${1:-/work/maps/map.yaml}
ROBOT_ID=${ROBOT_ID:-rasp-zero-01}
ZENOH_CONFIG=${ZENOH_CONFIG:-/repo/zenoh_remote.json5}
LOG_DIR=${LOG_DIR:-/tmp/dmc_nav2_realrobot_loc_noekf}
mkdir -p "$LOG_DIR"

cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

cleanup() {
  echo "[bringup-loc-noekf] stopping launched processes..."
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ros2 launch dmc_nav_bridge bridge_odom.launch.py \
  robot_id:="$ROBOT_ID" zenoh_config:="$ZENOH_CONFIG" >"$LOG_DIR/bridge.log" 2>&1 &
ros2 launch dmc_nav_bridge nav2_localization.launch.py \
  map:="$MAP_PATH" >"$LOG_DIR/nav2_localization.log" 2>&1 &

echo "[bringup-loc-noekf] robot_id=$ROBOT_ID zenoh_config=$ZENOH_CONFIG"
echo "[bringup-loc-noekf] waiting for topics/actions..."
sleep 10

echo "[bringup-loc-noekf] running with map=$MAP_PATH"
echo "[bringup-loc-noekf] logs: $LOG_DIR"
echo "[bringup-loc-noekf] Ctrl+C to stop all launched processes"
wait
