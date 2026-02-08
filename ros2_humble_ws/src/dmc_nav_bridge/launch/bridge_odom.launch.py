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
        ),
        Node(
            package='dmc_nav_bridge',
            executable='zenoh_odom_bridge',
            name='zenoh_odom_bridge',
            output='screen',
            parameters=['/work/src/dmc_nav_bridge/config/odom.yaml'],
        ),
        Node(
            package='dmc_nav_bridge',
            executable='zenoh_lidar_bridge',
            name='zenoh_lidar_bridge',
            output='screen',
            parameters=['/work/src/dmc_nav_bridge/config/lidar.yaml'],
        ),
    ])
