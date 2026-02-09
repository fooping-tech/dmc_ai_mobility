from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot_id = LaunchConfiguration('robot_id')
    zenoh_config = LaunchConfiguration('zenoh_config')

    return LaunchDescription([
        DeclareLaunchArgument('robot_id', default_value='rasp-zero-01'),
        DeclareLaunchArgument('zenoh_config', default_value='/work/../zenoh_remote.json5'),
        Node(
            package='dmc_nav_bridge',
            executable='cmdvel_to_zenoh',
            name='cmdvel_to_zenoh',
            output='screen',
            parameters=[
                '/work/src/dmc_nav_bridge/config/bridge.yaml',
                {'robot_id': robot_id, 'zenoh_config': zenoh_config},
            ],
        ),
        Node(
            package='dmc_nav_bridge',
            executable='zenoh_odom_bridge',
            name='zenoh_odom_bridge',
            output='screen',
            parameters=[
                '/work/src/dmc_nav_bridge/config/odom.yaml',
                {'robot_id': robot_id, 'zenoh_config': zenoh_config},
            ],
        ),
        Node(
            package='dmc_nav_bridge',
            executable='zenoh_lidar_bridge',
            name='zenoh_lidar_bridge',
            output='screen',
            parameters=[
                '/work/src/dmc_nav_bridge/config/lidar.yaml',
                {'robot_id': robot_id, 'zenoh_config': zenoh_config},
            ],
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_scan_tf',
            output='screen',
            arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'base_scan'],
        ),
    ])
