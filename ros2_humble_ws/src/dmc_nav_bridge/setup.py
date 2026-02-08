from setuptools import setup
package_name = 'dmc_nav_bridge'
setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bridge.launch.py']),
        ('share/' + package_name + '/config', ['config/bridge.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='bot-chan',
    maintainer_email='bot@example.com',
    description='ROS2 <-> dmc_ai_mobility bridge',
    license='Apache-2.0',
    entry_points={'console_scripts': ['cmdvel_to_zenoh = dmc_nav_bridge.cmdvel_to_zenoh:main']},
)
