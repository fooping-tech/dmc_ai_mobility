#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <x[m]> <y[m]> <yaw[deg]>"
  exit 1
fi
X="$1"
Y="$2"
YAW_DEG="$3"
python3 - <<PY
import math
x=float("$X"); y=float("$Y"); yaw=math.radians(float("$YAW_DEG"))
z=math.sin(yaw/2.0); w=math.cos(yaw/2.0)
print(f"{x} {y} {z} {w}")
PY
read X2 Y2 Z W < <(python3 - <<PY
import math
x=float("$X"); y=float("$Y"); yaw=math.radians(float("$YAW_DEG"))
print(x,y,math.sin(yaw/2.0),math.cos(yaw/2.0))
PY
)
cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: map}, pose: {position: {x: $X2, y: $Y2, z: 0.0}, orientation: {z: $Z, w: $W}}}}"
