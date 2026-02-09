FROM arm64v8/ros:humble-ros-base
SHELL ["/bin/bash", "-lc"]
RUN apt-get update && apt-get install -y \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-robot-localization \
    ros-humble-twist-mux \
    ros-humble-teleop-twist-keyboard \
    ros-humble-rviz2 \
    python3-pip \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir eclipse-zenoh
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
WORKDIR /work
