#!/usr/bin/env bash
set -euo pipefail

# ROS 2 Humble + Nav2 on Debian host via Docker (recommended for this machine)
# Usage:
#   bash scripts/bootstrap_ros2_humble_nav2_docker.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS="$ROOT/ros2_humble_ws"
mkdir -p "$WS/src"

cat > "$WS/Dockerfile" <<'EOF'
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-lc"]
RUN apt-get update && apt-get install -y \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-robot-localization \
    ros-humble-twist-mux \
    ros-humble-teleop-twist-keyboard \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
WORKDIR /work
EOF

cat > "$WS/run_nav2_container.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

docker build -t dmc-ros2-humble-nav2 -f "$ROOT/Dockerfile" "$ROOT"

docker run --rm -it \
  --net=host \
  --privileged \
  -e DISPLAY=${DISPLAY:-} \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$ROOT":/work \
  dmc-ros2-humble-nav2 \
  bash
EOF
chmod +x "$WS/run_nav2_container.sh"

echo "Created:"
echo "  $WS/Dockerfile"
echo "  $WS/run_nav2_container.sh"
echo "Next: bash $WS/run_nav2_container.sh"
