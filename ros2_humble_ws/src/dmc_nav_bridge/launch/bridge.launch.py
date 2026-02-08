from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='dmc_nav_bridge',
            executable='cmdvel_to_zenoh',
            name='cmdvel_to_zenoh',
            output='screen',
            parameters=['/work/src/dmc_nav_bridge/config/bridge.yaml'],
        )
    ])
