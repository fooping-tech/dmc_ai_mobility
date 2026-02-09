#!/usr/bin/env python3
import argparse
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

from PIL import Image


def load_map(map_yaml: Path):
    text = map_yaml.read_text()
    kv = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        k, v = line.split(':', 1)
        kv[k.strip()] = v.strip()

    image_rel = kv.get('image', 'map.pgm').strip().strip('"').strip("'")
    image_path = (map_yaml.parent / image_rel).resolve()
    resolution = float(kv.get('resolution', '0.05'))

    origin_raw = kv.get('origin', '[-5.0, -5.0, 0.0]').strip()
    origin_raw = origin_raw.strip('[]')
    ox, oy, oyaw = [float(x.strip()) for x in origin_raw.split(',')]

    occ_thresh = float(kv.get('occupied_thresh', '0.65'))

    img = Image.open(image_path).convert('L')
    w, h = img.size
    px = img.load()

    occ = [[False] * h for _ in range(w)]
    occ_pix = int(255 * (1.0 - occ_thresh))
    for x in range(w):
        for y in range(h):
            occ[x][y] = px[x, y] <= occ_pix

    return {
        'occ': occ,
        'w': w,
        'h': h,
        'resolution': resolution,
        'origin': (ox, oy, oyaw),
    }


def world_to_map(x, y, m):
    ox, oy, _ = m['origin']
    mx = int((x - ox) / m['resolution'])
    my = int((y - oy) / m['resolution'])
    # map image y is top-down, occupancy indexing here uses bottom-left map axis
    return mx, my


def is_occ_world(x, y, m):
    mx, my = world_to_map(x, y, m)
    if mx < 0 or my < 0 or mx >= m['w'] or my >= m['h']:
        return True
    # convert to image row index
    iy = m['h'] - 1 - my
    return m['occ'][mx][iy]


class FakeScanNode(Node):
    def __init__(self, args):
        super().__init__('fake_scan_from_map')
        self.m = load_map(Path(args.map))
        self.robot_x = args.robot_x
        self.robot_y = args.robot_y
        self.robot_yaw = args.robot_yaw
        self.frame = args.frame
        self.range_min = args.range_min
        self.range_max = args.range_max
        self.angle_min = -math.pi
        self.angle_max = math.pi
        self.angle_inc = math.radians(args.angle_deg)
        self.step = args.raycast_step
        self.pub = self.create_publisher(LaserScan, args.topic, 10)
        self.timer = self.create_timer(1.0 / args.hz, self.publish_scan)
        self.get_logger().info(f"loaded map={args.map}, topic={args.topic}, pose=({self.robot_x},{self.robot_y},{self.robot_yaw})")

    def raycast(self, angle):
        a = self.robot_yaw + angle
        d = self.range_min
        while d <= self.range_max:
            x = self.robot_x + d * math.cos(a)
            y = self.robot_y + d * math.sin(a)
            if is_occ_world(x, y, self.m):
                return d
            d += self.step
        return float('inf')

    def publish_scan(self):
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame
        msg.angle_min = self.angle_min
        msg.angle_max = self.angle_max
        msg.angle_increment = self.angle_inc
        msg.time_increment = 0.0
        msg.scan_time = 0.0
        msg.range_min = self.range_min
        msg.range_max = self.range_max

        n = int((self.angle_max - self.angle_min) / self.angle_inc)
        ranges = []
        for i in range(n):
            ang = self.angle_min + i * self.angle_inc
            ranges.append(self.raycast(ang))
        msg.ranges = ranges
        self.pub.publish(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', required=True)
    ap.add_argument('--topic', default='/scan')
    ap.add_argument('--frame', default='base_scan')
    ap.add_argument('--robot-x', type=float, default=0.0)
    ap.add_argument('--robot-y', type=float, default=0.0)
    ap.add_argument('--robot-yaw', type=float, default=0.0)
    ap.add_argument('--hz', type=float, default=8.0)
    ap.add_argument('--angle-deg', type=float, default=1.0)
    ap.add_argument('--range-min', type=float, default=0.05)
    ap.add_argument('--range-max', type=float, default=6.0)
    ap.add_argument('--raycast-step', type=float, default=0.03)
    ap.add_argument('--duration', type=float, default=0.0)
    args = ap.parse_args()

    rclpy.init()
    node = FakeScanNode(args)
    if args.duration > 0:
        end = time.time() + args.duration
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(node, timeout_sec=0.2)
    else:
        rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
