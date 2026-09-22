import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_gazebo = get_package_share_directory("warehouse_gazebo")
    pkg_description = get_package_share_directory("warehouse_description")

    default_world = os.path.join(pkg_gazebo, "worlds", "warehouse_stage1.world")
    xacro_file = os.path.join(pkg_description, "urdf", "warehouse_robot.urdf.xacro")

    # base_link 原点在小车底部上方 0.10m，按这个高度生成可以避免落地时砸一下
    spawn_z = "0.10"

    return LaunchDescription([
        DeclareLaunchArgument("world", default_value=default_world),

        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{
                "robot_description": Command(["xacro ", xacro_file]),
                "use_sim_time": True,
            }],
        ),

        # gzserver/gzclient 是 Gazebo 自带的系统二进制（/usr/bin），不在 gazebo_ros 的
        # libexec 目录里，所以必须用 ExecuteProcess 调，不能用 Node(package="gazebo_ros")
        ExecuteProcess(
            cmd=["gzserver",
                 "-s", "libgazebo_ros_init.so",
                 "-s", "libgazebo_ros_factory.so",
                 LaunchConfiguration("world")],
            output="screen",
        ),

        ExecuteProcess(
            cmd=["gzclient"],
            output="screen",
        ),

        Node(
            package="gazebo_ros",
            executable="spawn_entity.py",
            name="spawn_warehouse_robot",
            output="screen",
            arguments=[
                "-topic", "robot_description",
                "-entity", "warehouse_robot",
                "-x", "0", "-y", "-4", "-z", spawn_z,
                "-Y", "0.0",
            ],
        ),
    ])
