#!/usr/bin/env bash
set -euo pipefail

cd /work
source /opt/ros/humble/setup.bash
source /work/install/setup.bash

TIMEOUT=${TIMEOUT:-8}
FAIL=0

check() {
  local label="$1"
  local cmd="$2"
  set +e
  timeout "$TIMEOUT" bash -lc "$cmd" >/dev/null 2>&1
  local rc=$?
  set -e
  if [ $rc -eq 0 ]; then
    echo "[ok] $label"
  else
    echo "[ng] $label"
    FAIL=1
  fi
}

echo "[preflight] checking Nav2 real-robot prerequisites"
check "/scan topic" "ros2 topic echo /scan --once"
check "/odom topic" "ros2 topic echo /odom --once"
check "/odom_filtered topic" "ros2 topic echo /odom_filtered --once"
check "TF odom->base_link" "ros2 run tf2_ros tf2_echo odom base_link"
check "TF base_link->base_scan" "ros2 run tf2_ros tf2_echo base_link base_scan"
check "action /navigate_to_pose" "ros2 action list | grep -q /navigate_to_pose"

if [ $FAIL -eq 0 ]; then
  echo "[preflight] PASS"
  exit 0
else
  echo "[preflight] FAIL (check logs/topics above)"
  exit 1
fi
