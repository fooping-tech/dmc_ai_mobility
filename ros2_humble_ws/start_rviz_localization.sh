#!/usr/bin/env bash
set -euo pipefail

cd /work
set +u
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
set -u

rviz2 -d /work/config/rviz/localization.rviz
