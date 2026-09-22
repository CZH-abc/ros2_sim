import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_nav = get_package_share_directory("warehouse_nav")
    params_file = os.path.join(pkg_nav, "config", "mapper_params.yaml")

    return LaunchDescription([
        # 虚拟机里 RViz 若把画面搞崩（VMware 3D 加速常见），用 rviz:=false 单独关掉它，
        # 不影响建图本身
        DeclareLaunchArgument("rviz", default_value="true"),

        Node(
            package="slam_toolbox",
            executable="async_slam_toolbox_node",
            # 节点名必须和 mapper_params.yaml 顶层那个 key 一致，否则参数一条都读不进去
            name="slam_toolbox",
            output="screen",
            parameters=[params_file, {"use_sim_time": True}],
        ),

        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            output="screen",
            parameters=[{"use_sim_time": True}],
            condition=IfCondition(LaunchConfiguration("rviz")),
        ),
    ])
