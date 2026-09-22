"""阶段 5：仓库任务调度器。

它自己不会开车，也不看地图。它只做一件事：
    按 warehouse_waypoints.yaml 的顺序，一个一个把目标点交给 Nav2 的
    navigate_to_pose 动作，等它跑完再交下一个。

真正干活的还是阶段 4 那套 Nav2：这里发一个目标 = 一次完整的"规划 + 行驶 + 到点"。

用法：
    ros2 launch warehourse_tasks tasks.launch.py                          # 起节点
    ros2 topic pub --once /task_cmd std_msgs/msg/String "{data: start}"   # 发车
    ros2 topic pub --once /task_cmd std_msgs/msg/String "{data: stop}"    # 急停
    ros2 topic echo /task_status                                          # 看进度，Ctrl+C 退出
"""

import math

import yaml

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String


class TaskSequencer(Node):
    def __init__(self):
        # 注意：use_sim_time 不要在这里 declare，rclpy 已经替每个节点声明好了，
        # 再声明一次会抛 ParameterAlreadyDeclaredException，launch 直接起不来。
        super().__init__("task_sequencer")

        self.declare_parameter("waypoints_file", "")
        self.waypoints = self._load_waypoints(
            self.get_parameter("waypoints_file").value
        )

        self._client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._status_pub = self.create_publisher(String, "task_status", 10)
        self._cmd_sub = self.create_subscription(
            String, "task_cmd", self._on_cmd, 10
        )

        # -1 表示闲着；否则正在跑 self.waypoints[self._index]
        self._index = -1
        self._loop = self._loop_cfg and bool(self.waypoints)
        self._goal_handle = None
        self._dwell_timer = None
        self._retry_timer = None
        self._retries = 0

        self.get_logger().info(
            f"任务节点就绪，路线共 {len(self.waypoints)} 个点，"
            f"往 /task_cmd 发 start 发车，发 stop 停车"
        )

    # ---------- 配置 ----------
    def _load_waypoints(self, path):
        self._loop_cfg = False
        if not path:
            self.get_logger().error(
                "没传 waypoints_file 参数，路线是空的。"
                "请用 tasks.launch.py 起，或 -p waypoints_file:=/完整路径.yaml"
            )
            return []
        try:
            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except FileNotFoundError:
            self.get_logger().error(f"找不到路线文件：{path}")
            return []

        points = cfg.get("waypoints") or []
        self._loop_cfg = bool(cfg.get("loop", False))
        if not points:
            self.get_logger().error(f"{path} 里的 waypoints 是空的")
            return []
        self.get_logger().info(
            "读到目标点：" + " -> ".join(str(p["name"]) for p in points)
        )
        return points

    # ---------- 对外接口 ----------
    def _on_cmd(self, msg):
        cmd = msg.data.strip().lower()
        if cmd == "start":
            if self._index >= 0:
                self._report("任务已经在跑了，要重发请先 stop")
                return
            if not self.waypoints:
                self._report("路线为空，无法启动")
                return
            # _index 从 -1 开始，_advance 会把它推到 0
            self._index = -1
            self._advance()
        elif cmd == "stop":
            self._cancel_current()
        else:
            self._report(f"不认识的指令 '{msg.data}'，只接受 start / stop")

    # ---------- 流程推进 ----------
    def _advance(self):
        self._index += 1
        if self._index >= len(self.waypoints):
            if self._loop:
                self._index = 0
                self._report("一圈跑完，loop=true，再来一圈")
            else:
                self._index = -1
                self._report("全部目标点已完成，任务结束")
                return
        self._send_current()

    def _send_current(self):
        # 绝不能在回调里 wait_for_server：它会占死唯一那根执行器线程，
        # 结果是"等别人 ready"和"别人靠回调才 ready"互相等，只能靠超时脱身。
        # 正确姿势：查一下，没就绪就挂个 1 秒的一次性定时器再查。
        self._retries = 0
        self._send_or_retry()

    def _send_or_retry(self):
        if self._client.server_is_ready():
            self._start_goal()
            return
        if self._retries >= 10:
            self._report("重试 10 秒还没连上 navigate_to_pose 动作服务器，Nav2 起了吗？任务中止")
            self._index = -1
            return
        self._retries += 1
        if self._retries == 1:
            self._report("还没连上 navigate_to_pose，每秒重试一次，最多 10 次")
        self._retry_timer = self.create_timer(1.0, self._on_retry_tick)

    def _on_retry_tick(self):
        timer, self._retry_timer = self._retry_timer, None
        if timer is not None:
            timer.cancel()
        if self._index < 0:
            return  # 等待期间被 stop 了
        self._send_or_retry()

    def _start_goal(self):
        wp = self.waypoints[self._index]
        goal = NavigateToPose.Goal()
        goal.pose = self._to_pose_stamped(wp)
        self._client.send_goal_async(goal).add_done_callback(self._on_goal_accepted)

    def _on_goal_accepted(self, future):
        if self._index < 0:
            return  # start 之后又被 stop 了，结果回来也不认
        handle = future.result()
        wp = self.waypoints[self._index]
        if not handle.accepted:
            self._report(f"Nav2 拒绝了 {wp['name']}（目标点在墙里，或车被障碍物包围），任务中止")
            self._index = -1
            return

        self._goal_handle = handle
        tag = f"[{self._index + 1}/{len(self.waypoints)}]"
        self._report(f"{tag} 前往 {wp['name']} ({wp['x']:.2f}, {wp['y']:.2f})")
        handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        self._goal_handle = None
        if self._index < 0:
            return  # 已被 stop，取消的返回结果不用管
        wp = self.waypoints[self._index]
        status = future.result().status
        if status != GoalStatus.STATUS_SUCCEEDED:
            self._report(f"{wp['name']} 没走到（Nav2 状态码 {status}），任务中止")
            self._index = -1
            return

        self._report(f"{wp['name']} 到位")
        dwell = float(wp.get("dwell_sec", 0.0))
        if dwell > 0.0:
            # 不能 sleep：一 sleep 整个节点冻住，stop 指令和状态发布全都收不到。
            # 用一次性定时器，回调里自己 cancel。
            self._report(f"停留 {dwell:.0f} 秒（模拟扫码/取货）")
            self._dwell_timer = self.create_timer(dwell, self._after_dwell)
        else:
            self._advance()

    def _after_dwell(self):
        if self._dwell_timer is not None:
            self._dwell_timer.cancel()
            self._dwell_timer = None
        if self._index < 0:
            return  # 停留期间被 stop 了
        self._advance()

    def _cancel_current(self):
        if self._dwell_timer is not None:
            self._dwell_timer.cancel()
            self._dwell_timer = None
        handle, self._goal_handle = self._goal_handle, None
        self._index = -1
        if handle is None:
            self._report("当前没有进行中的动作，已置为空闲")
            return
        handle.cancel_goal_async()
        self._report("已发送取消，车会减速停住")

    # ---------- 工具 ----------
    def _to_pose_stamped(self, wp):
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(wp["x"])
        pose.pose.position.y = float(wp["y"])
        pose.pose.position.z = 0.0
        # 平面转角换四元数：差速车只有绕 z 轴转，所以只有 z 和 w 非零
        half = float(wp.get("yaw", 0.0)) / 2.0
        pose.pose.orientation.z = math.sin(half)
        pose.pose.orientation.w = math.cos(half)
        return pose

    def _report(self, text):
        self.get_logger().info(text)
        self._status_pub.publish(String(data=text))


def main():
    rclpy.init()
    node = TaskSequencer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
