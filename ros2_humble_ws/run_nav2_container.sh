#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

docker build -t dmc-ros2-humble-nav2 -f "$ROOT/Dockerfile" "$ROOT"

docker run --rm -it \
  --net=host \
  --privileged \
  -e DISPLAY=${DISPLAY:-} \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$(cd "$ROOT/.." && pwd)":/repo \
  -v "$ROOT":/work \
  dmc-ros2-humble-nav2 \
  bash
