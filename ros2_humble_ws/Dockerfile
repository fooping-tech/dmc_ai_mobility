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
