from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    xacro_file = PathJoinSubstitution([
        FindPackageShare("warehouse_description"),
        "urdf",
        "warehouse_robot.urdf.xacro",
    ])

    return LaunchDescription([
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            parameters=[{
                "robot_description": Command(["xacro ", xacro_file])
            }],
        ),

        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            name="joint_state_publisher_gui",
        ),

        # 这里原本有一条静态 map -> odom，阶段 3 起已删除：那条变换归 slam_toolbox 实时
        # 计算并发布，静态节点会和它抢同一个 tf，表现为 RViz 里整台车突然跳回原点
    ])