from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=['/work/src/dmc_nav_bridge/config/ekf.yaml'],
            remappings=[('/odometry/filtered', '/odom_filtered')],
        ),
    ])
