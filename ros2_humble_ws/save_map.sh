#!/usr/bin/env bash
set -euo pipefail
NAME="${1:-map}"
cd /work
mkdir -p maps
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u
ros2 run nav2_map_server map_saver_cli \
  -f /work/maps/${NAME} \
  --ros-args \
  -p map_subscribe_transient_local:=true \
  -p save_map_timeout:=10.0

echo "saved: /work/maps/${NAME}.yaml"
