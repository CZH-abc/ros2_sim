"""阶段 5：起任务调度节点。

前提：阶段 4 的 nav.launch.py 已经把 Nav2 拉起来了（能看到 "Managed nodes are active"）。
用法：
    ros2 launch warehourse_tasks tasks.launch.py
    ros2 launch warehourse_tasks tasks.launch.py waypoints_file:=/自己的/路线.yaml
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_tasks = get_package_share_directory("warehourse_tasks")
    default_waypoints = os.path.join(pkg_tasks, "config", "warehouse_waypoints.yaml")

    return LaunchDescription([
        DeclareLaunchArgument("waypoints_file", default_value=default_waypoints,
                              description="路线 yaml 的完整路径"),
        Node(
            package="warehourse_tasks",
            executable="task_sequencer",
            name="task_sequencer",
            output="screen",
            # use_sim_time 必须是 True：否则我们的时钟跟 Gazebo 对不上，
            # 目标点时间戳会被 Nav2 当成"过期"直接丢掉，车一步都不走。
            parameters=[
                {"use_sim_time": True},
                {"waypoints_file": LaunchConfiguration("waypoints_file")},
            ],
        ),
    ])
