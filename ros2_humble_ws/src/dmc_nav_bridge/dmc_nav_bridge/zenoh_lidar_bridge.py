import json
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

try:
    import zenoh
except Exception:
    zenoh = None


class ZenohLidarBridge(Node):
    def __init__(self):
        super().__init__('zenoh_lidar_bridge')
        self.declare_parameter('robot_id', 'rasp-zero-01')
        self.declare_parameter('zenoh_config', '/work/../zenoh_remote.json5')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('scan_frame', 'base_scan')
        self.declare_parameter('angle_min', -math.pi)
        self.declare_parameter('angle_max', math.pi)
        self.declare_parameter('angle_increment', math.radians(1.0))
        self.declare_parameter('range_min', 0.05)
        self.declare_parameter('range_max', 5.0)

        self.robot_id = self.get_parameter('robot_id').value
        self.scan_topic = self.get_parameter('scan_topic').value
        self.scan_frame = self.get_parameter('scan_frame').value
        self.angle_min = float(self.get_parameter('angle_min').value)
        self.angle_max = float(self.get_parameter('angle_max').value)
        self.angle_inc = float(self.get_parameter('angle_increment').value)
        self.range_min = float(self.get_parameter('range_min').value)
        self.range_max = float(self.get_parameter('range_max').value)

        self.key = f'dmc_robo/{self.robot_id}/lidar/scan'
        self.pub = self.create_publisher(LaserScan, self.scan_topic, 10)
        self.last_ts = time.monotonic()

        self.session = None
        if zenoh is None:
            self.get_logger().error('zenoh python package not found. pip install eclipse-zenoh')
            return

        try:
            zconf = self.get_parameter('zenoh_config').value
            conf = zenoh.Config.from_file(zconf)
            self.session = zenoh.open(conf)
            self.sub = self.session.declare_subscriber(self.key, self.on_scan)
            self.get_logger().info(f'subscribed: {self.key}')
        except Exception as e:
            self.get_logger().error(f'zenoh subscribe failed: {e}')

    def on_scan(self, sample):
        try:
            data = json.loads(sample.payload.to_bytes().decode('utf-8'))
            points = data.get('points', [])
            if not points:
                return

            n = int(round((self.angle_max - self.angle_min) / self.angle_inc)) + 1
            ranges = [float('inf')] * max(1, n)

            for p in points:
                a = float(p.get('angle_rad', 0.0))
                r = float(p.get('range_m', float('inf')))
                if not math.isfinite(r):
                    continue
                if r < self.range_min or r > self.range_max:
                    continue
                idx = int(round((a - self.angle_min) / self.angle_inc))
                if 0 <= idx < n and r < ranges[idx]:
                    ranges[idx] = r

            msg = LaserScan()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.scan_frame
            msg.angle_min = self.angle_min
            msg.angle_max = self.angle_max
            msg.angle_increment = self.angle_inc
            now = time.monotonic()
            msg.scan_time = max(1e-3, now - self.last_ts)
            self.last_ts = now
            msg.time_increment = 0.0
            msg.range_min = self.range_min
            msg.range_max = self.range_max
            msg.ranges = ranges
            self.pub.publish(msg)
        except Exception:
            pass


def main():
    rclpy.init()
    node = ZenohLidarBridge()
    try:
        rclpy.spin(node)
    finally:
        if node.session is not None:
            node.session.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
