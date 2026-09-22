"""阶段 4：拿阶段 3 存下来的静态地图做定位 + 导航。

用法（前提是 Gazebo 里的小车已经跑起来了）：
    ros2 launch warehouse_nav nav.launch.py
换地图文件：
    ros2 launch warehouse_nav nav.launch.py map:=/完整路径/xxx.yaml

这里刻意不用 nav2_bringup 的 navigation_launch.py，而是把每个节点一条条列出来。
原因：出问题时要能一眼看出是哪个节点没起来。Include 进来的话，
日志里几十个节点混在一起，初学者根本分不清。
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_nav = get_package_share_directory("warehouse_nav")
    nav2_params = os.path.join(pkg_nav, "config", "nav2_params.yaml")
    default_map = os.path.join(pkg_nav, "maps", "warehouse_map.yaml")
    default_rviz = os.path.join(pkg_nav, "config", "nav_view.rviz")

    map_yaml = LaunchConfiguration("map")
    use_rviz = LaunchConfiguration("rviz")

    # 所有节点都从同一个 yaml 里取自己那一节，所以参数只写 parameters=[nav2_params]。
    # use_sim_time 已经写在 yaml 的每一个 ros__parameters 里了，不用再重复传。
    common = dict(output="screen", parameters=[nav2_params])

    return LaunchDescription([
        DeclareLaunchArgument("map", default_value=default_map,
                              description="要加载的地图 yaml（不是 pgm）"),
        DeclareLaunchArgument("rviz", default_value="true",
                              description="false = 不开 RViz 窗口"),

        # ---------- 第一层：定位（我在哪） ----------
        # yaml_filename 必须走 parameters，不能当位置参数传（arguments 里只放 -r/--remap 这类）
        Node(package="nav2_map_server", executable="map_server", name="map_server",
             output="screen",
             parameters=[nav2_params, {"yaml_filename": map_yaml}]),
        Node(package="nav2_amcl", executable="amcl", name="amcl", **common),
        Node(package="nav2_lifecycle_manager", executable="lifecycle_manager",
             name="lifecycle_manager_map", output="screen",
             parameters=[nav2_params, {"autostart": True}]),

        # ---------- 第二层：控制与规划（怎么去） ----------
        # controller_server 会顺便把 local_costmap 建起来
        Node(package="nav2_controller", executable="controller_server",
             name="controller_server", **common),
        Node(package="nav2_smoother", executable="smoother_server",
             name="smoother_server", **common),
        # planner_server 会顺便把 global_costmap 建起来，所以排在 controller 之后
        Node(package="nav2_planner", executable="planner_server",
             name="planner_server", **common),
        Node(package="nav2_behaviors", executable="behavior_server",
             name="behavior_server", **common),
        # bt_navigator 是把上面这些串起来的那个"总指挥"，对外提供 navigate_to_pose 动作
        Node(package="nav2_bt_navigator", executable="bt_navigator",
             name="bt_navigator", **common),
        Node(package="nav2_waypoint_follower", executable="waypoint_follower",
             name="waypoint_follower", **common),
        Node(package="nav2_lifecycle_manager", executable="lifecycle_manager",
             name="lifecycle_manager_navigation", output="screen",
             parameters=[nav2_params, {"autostart": True}]),

        Node(package="rviz2", executable="rviz2", name="rviz2", output="screen",
             arguments=["-d", default_rviz],
             parameters=[{"use_sim_time": True}],
             condition=IfCondition(use_rviz)),
    ])
