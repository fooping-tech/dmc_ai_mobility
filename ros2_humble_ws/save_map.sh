#!/usr/bin/env bash
set -euo pipefail
NAME="${1:-map}"
cd /work
mkdir -p maps
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
ros2 run nav2_map_server map_saver_cli -f /work/maps/${NAME}
echo "saved: /work/maps/${NAME}.yaml"
