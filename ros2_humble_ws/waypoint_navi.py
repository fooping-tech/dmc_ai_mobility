#!/usr/bin/env python3
import argparse
import json
import math
import time
from typing import List, Tuple

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose


def yaw_to_quat(yaw: float):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def parse_waypoint_text(text: str) -> List[Tuple[float, float, float]]:
    # format: "x,y,yaw;x,y,yaw;..."
    out = []
    for chunk in text.split(';'):
        chunk = chunk.strip()
        if not chunk:
            continue
        x, y, yaw = [float(v.strip()) for v in chunk.split(',')]
        out.append((x, y, yaw))
    return out


def load_waypoints_file(path: str) -> Tuple[Tuple[float, float, float] | None, List[Tuple[float, float, float]]]:
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Try JSON first (stdlib only)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # YAML optional fallback
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError('YAML file detected but PyYAML is not installed. Use JSON or install python3-yaml.') from e
        data = yaml.safe_load(raw)

    initial_pose = None
    if data.get('initial_pose'):
        ip = data['initial_pose']
        initial_pose = (float(ip[0]), float(ip[1]), float(ip[2]))

    wps = []
    for p in data.get('waypoints', []):
        wps.append((float(p[0]), float(p[1]), float(p[2])))

    return initial_pose, wps


class WaypointNavi(Node):
    def __init__(self):
        super().__init__('waypoint_navi')
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

    def publish_initial_pose(self, x: float, y: float, yaw: float):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        qx, qy, qz, qw = yaw_to_quat(yaw)
        msg.pose.pose.orientation.x = qx
        msg.pose.pose.orientation.y = qy
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        # simple diagonal covariance
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.0685
        self.initial_pose_pub.publish(msg)
        self.get_logger().info(f'published initialpose: x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}')

    def send_goal_and_wait(self, x: float, y: float, yaw: float) -> bool:
        while not self.nav_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().info('waiting for /navigate_to_pose action server...')

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        qx, qy, qz, qw = yaw_to_quat(yaw)
        goal.pose.pose.orientation.x = qx
        goal.pose.pose.orientation.y = qy
        goal.pose.pose.orientation.z = qz
        goal.pose.pose.orientation.w = qw

        self.get_logger().info(f'send goal: x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}')
        send_fut = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_fut)
        goal_handle = send_fut.result()

        if not goal_handle or not goal_handle.accepted:
            self.get_logger().error('goal rejected')
            return False

        result_fut = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_fut)
        result = result_fut.result()
        if result is None:
            self.get_logger().error('no result from action server')
            return False

        status = int(result.status)
        if status == 4:  # STATUS_SUCCEEDED
            self.get_logger().info('goal succeeded')
            return True

        self.get_logger().warn(f'goal finished with status={status}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Sequential waypoint navigation for Nav2')
    parser.add_argument('--waypoints', default='', help='"x,y,yaw;x,y,yaw;..."')
    parser.add_argument('--file', default='', help='JSON/YAML file with initial_pose and waypoints')
    parser.add_argument('--set-initial-pose', action='store_true', help='publish /initialpose before first goal')
    parser.add_argument('--initial-pose', default='', help='"x,y,yaw" used with --set-initial-pose')
    parser.add_argument('--sleep-after-initial', type=float, default=1.0, help='seconds to wait after /initialpose publish')
    args = parser.parse_args()

    initial_pose = None
    waypoints: List[Tuple[float, float, float]] = []

    if args.file:
        f_ip, f_wps = load_waypoints_file(args.file)
        if f_ip:
            initial_pose = f_ip
        waypoints.extend(f_wps)

    if args.waypoints:
        waypoints.extend(parse_waypoint_text(args.waypoints))

    if args.initial_pose:
        vals = [float(v.strip()) for v in args.initial_pose.split(',')]
        initial_pose = (vals[0], vals[1], vals[2])

    if not waypoints:
        raise SystemExit('No waypoints specified. Use --waypoints or --file')

    rclpy.init()
    node = WaypointNavi()

    try:
        if args.set_initial_pose and initial_pose is not None:
            node.publish_initial_pose(*initial_pose)
            time.sleep(args.sleep_after_initial)

        for idx, (x, y, yaw) in enumerate(waypoints, start=1):
            node.get_logger().info(f'waypoint {idx}/{len(waypoints)}')
            ok = node.send_goal_and_wait(x, y, yaw)
            if not ok:
                node.get_logger().error(f'stopped at waypoint {idx}')
                break
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
