import json
import math
import time

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion, TransformStamped
from tf2_ros import TransformBroadcaster

try:
    import zenoh
except Exception:
    zenoh = None


def yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.w = math.cos(yaw * 0.5)
    q.z = math.sin(yaw * 0.5)
    q.x = 0.0
    q.y = 0.0
    return q


class ZenohOdomBridge(Node):
    def __init__(self):
        super().__init__('zenoh_odom_bridge')
        self.declare_parameter('robot_id', 'rasp-zero-01')
        self.declare_parameter('zenoh_config', '/work/../zenoh_remote.json5')
        self.declare_parameter('wheel_base_m', 0.12)
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('hz', 30.0)

        self.robot_id = self.get_parameter('robot_id').value
        self.key = f'dmc_robo/{self.robot_id}/motor/telemetry'
        self.wheel_base = float(self.get_parameter('wheel_base_m').value)
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.publish_tf = bool(self.get_parameter('publish_tf').value)

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.v_l = 0.0
        self.v_r = 0.0
        self.last_t = time.monotonic()

        self.odom_pub = self.create_publisher(Odometry, '/odom', 20)
        self.tf_broadcaster = TransformBroadcaster(self)

        self.session = None
        if zenoh is None:
            self.get_logger().error('zenoh python package not found. pip install eclipse-zenoh')
        else:
            try:
                zconf = self.get_parameter('zenoh_config').value
                conf = zenoh.Config.from_file(zconf)
                self.session = zenoh.open(conf)
                self.sub = self.session.declare_subscriber(self.key, self.on_telemetry)
                self.get_logger().info(f'subscribed: {self.key}')
            except Exception as e:
                self.get_logger().error(f'zenoh subscribe failed: {e}')

        hz = float(self.get_parameter('hz').value)
        self.timer = self.create_timer(1.0 / max(1.0, hz), self.on_timer)

    def on_telemetry(self, sample):
        try:
            data = json.loads(sample.payload.to_bytes().decode('utf-8'))
            vl = data.get('cmd_v_l', data.get('v_l', 0.0))
            vr = data.get('cmd_v_r', data.get('v_r', 0.0))
            self.v_l = float(vl or 0.0)
            self.v_r = float(vr or 0.0)
        except Exception:
            pass

    def on_timer(self):
        now = time.monotonic()
        dt = max(1e-3, now - self.last_t)
        self.last_t = now

        v = 0.5 * (self.v_l + self.v_r)
        w = (self.v_r - self.v_l) / max(1e-6, self.wheel_base)

        self.yaw += w * dt
        self.x += v * math.cos(self.yaw) * dt
        self.y += v * math.sin(self.yaw) * dt

        stamp = self.get_clock().now().to_msg()
        q = yaw_to_quat(self.yaw)

        od = Odometry()
        od.header.stamp = stamp
        od.header.frame_id = self.odom_frame
        od.child_frame_id = self.base_frame
        od.pose.pose.position.x = self.x
        od.pose.pose.position.y = self.y
        od.pose.pose.orientation = q
        od.twist.twist.linear.x = v
        od.twist.twist.angular.z = w
        self.odom_pub.publish(od)

        if self.publish_tf:
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = self.odom_frame
            tf.child_frame_id = self.base_frame
            tf.transform.translation.x = self.x
            tf.transform.translation.y = self.y
            tf.transform.rotation = q
            self.tf_broadcaster.sendTransform(tf)


def main():
    rclpy.init()
    node = ZenohOdomBridge()
    try:
        rclpy.spin(node)
    finally:
        if node.session is not None:
            node.session.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
