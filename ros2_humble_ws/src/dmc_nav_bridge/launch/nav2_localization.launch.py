from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    nav2_dir = get_package_share_directory('nav2_bringup')
    map_path = LaunchConfiguration('map')

    return LaunchDescription([
        DeclareLaunchArgument('map', default_value='/work/maps/map.yaml'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([nav2_dir, '/launch/bringup_launch.py']),
            launch_arguments={
                'slam': 'False',
                'use_sim_time': 'False',
                'map': map_path,
                'params_file': '/work/src/dmc_nav_bridge/config/nav2_params.yaml',
                'autostart': 'True',
            }.items(),
        )
    ])
