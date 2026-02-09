from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    nav2_dir = get_package_share_directory('nav2_bringup')
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([nav2_dir, '/launch/bringup_launch.py']),
            launch_arguments={
                'slam': 'False',
                'use_sim_time': 'False',
                'map': '/work/maps/map.yaml',
                'params_file': '/work/src/dmc_nav_bridge/config/nav2_params.yaml',
                'autostart': 'True',
            }.items(),
        )
    ])
