from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    robot_id = LaunchConfiguration('robot_id')
    zenoh_config = LaunchConfiguration('zenoh_config')
    odom_source = LaunchConfiguration('odom_source')

    use_wheel = PythonExpression(["'", odom_source, "' == 'wheel'"])
    use_rf2o = PythonExpression(["'", odom_source, "' == 'rf2o'"])

    return LaunchDescription([
        DeclareLaunchArgument('robot_id', default_value='rasp-zero-01'),
        DeclareLaunchArgument('zenoh_config', default_value='/work/../zenoh_remote.json5'),
        DeclareLaunchArgument('odom_source', default_value='wheel'),  # wheel | rf2o
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
            condition=IfCondition(use_wheel),
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
            package='rf2o_laser_odometry',
            executable='rf2o_laser_odometry_node',
            name='rf2o_laser_odometry',
            output='screen',
            condition=IfCondition(use_rf2o),
            parameters=['/work/src/dmc_nav_bridge/config/rf2o.yaml'],
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_scan_tf',
            output='screen',
            arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'base_scan'],
        ),
    ])
