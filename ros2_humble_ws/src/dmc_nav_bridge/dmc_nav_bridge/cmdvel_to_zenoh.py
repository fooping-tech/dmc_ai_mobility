import json
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

try:
    import zenoh
except Exception:
    zenoh = None


class CmdVelToZenoh(Node):
    def __init__(self):
        super().__init__('cmdvel_to_zenoh')
        self.declare_parameter('robot_id', 'rasp-zero-01')
        self.declare_parameter('zenoh_config', '/work/../zenoh_remote.json5')
        self.declare_parameter('wheel_base_m', 0.12)
        self.declare_parameter('max_wheel_mps', 0.25)
        self.declare_parameter('deadman_ms', 250)

        self.robot_id = self.get_parameter('robot_id').value
        self.wheel_base = float(self.get_parameter('wheel_base_m').value)
        self.max_wheel = float(self.get_parameter('max_wheel_mps').value)
        self.deadman_ms = int(self.get_parameter('deadman_ms').value)
        zconf = self.get_parameter('zenoh_config').value
        self.key = f'dmc_robo/{self.robot_id}/motor/cmd'
        self.seq = 0
        self.session = None

        if zenoh is None:
            self.get_logger().error('zenoh python package not found. pip install eclipse-zenoh')
        else:
            try:
                conf = zenoh.Config.from_file(zconf)
                self.session = zenoh.open(conf)
                self.get_logger().info(f'zenoh connected: key={self.key}')
            except Exception as e:
                self.get_logger().error(f'zenoh open failed: {e}')

        self.sub = self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 20)

    def clamp(self, v):
        return max(-self.max_wheel, min(self.max_wheel, v))

    def on_cmd(self, msg: Twist):
        v = float(msg.linear.x)
        w = float(msg.angular.z)
        v_l = self.clamp(v - 0.5 * self.wheel_base * w)
        v_r = self.clamp(v + 0.5 * self.wheel_base * w)
        payload = {
            'v_l': v_l,
            'v_r': v_r,
            'unit': 'mps',
            'deadman_ms': self.deadman_ms,
            'seq': self.seq,
            'ts_ms': int(time.time() * 1000),
        }
        self.seq += 1
        if self.session is not None:
            self.session.put(self.key, json.dumps(payload).encode('utf-8'))


def main():
    rclpy.init()
    node = CmdVelToZenoh()
    try:
        rclpy.spin(node)
    finally:
        if node.session is not None:
            node.session.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
