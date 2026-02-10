#!/usr/bin/env python3
import math
import threading
from dataclasses import dataclass, asdict
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nav_msgs.msg import OccupancyGrid, Odometry
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped


@dataclass
class GoalState:
    status: str = "idle"
    detail: str = ""
    accepted: Optional[bool] = None


class GoalRequest(BaseModel):
    x: float
    y: float
    yaw_deg: float = 0.0


class RosNav2Bridge(Node):
    def __init__(self):
        super().__init__("web_nav2_ui_bridge")
        self.map_msg: Optional[OccupancyGrid] = None
        self.odom_msg: Optional[Odometry] = None
        self.goal_state = GoalState()

        self.create_subscription(OccupancyGrid, "/map", self._map_cb, 10)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

    def _map_cb(self, msg: OccupancyGrid):
        self.map_msg = msg

    def _odom_cb(self, msg: Odometry):
        self.odom_msg = msg

    def get_map(self):
        if self.map_msg is None:
            return None
        m = self.map_msg
        return {
            "resolution": m.info.resolution,
            "width": m.info.width,
            "height": m.info.height,
            "origin": {
                "x": m.info.origin.position.x,
                "y": m.info.origin.position.y,
            },
            "data": list(m.data),
        }

    def get_pose(self):
        if self.odom_msg is None:
            return None
        p = self.odom_msg.pose.pose
        return {
            "x": p.position.x,
            "y": p.position.y,
            "qx": p.orientation.x,
            "qy": p.orientation.y,
            "qz": p.orientation.z,
            "qw": p.orientation.w,
        }

    def send_goal(self, x: float, y: float, yaw_deg: float):
        if not self.nav_client.wait_for_server(timeout_sec=3.0):
            raise RuntimeError("/navigate_to_pose is not available")

        yaw = math.radians(yaw_deg)
        z = math.sin(yaw / 2.0)
        w = math.cos(yaw / 2.0)

        goal = NavigateToPose.Goal()
        ps = PoseStamped()
        ps.header.frame_id = "map"
        ps.pose.position.x = x
        ps.pose.position.y = y
        ps.pose.orientation.z = z
        ps.pose.orientation.w = w
        goal.pose = ps

        self.goal_state = GoalState(status="sending", detail="Sending goal", accepted=None)

        send_future = self.nav_client.send_goal_async(goal)

        def _on_goal_response(fut):
            goal_handle = fut.result()
            if goal_handle is None:
                self.goal_state = GoalState(status="error", detail="No goal handle", accepted=False)
                return
            if not goal_handle.accepted:
                self.goal_state = GoalState(status="rejected", detail="Goal rejected", accepted=False)
                return

            self.goal_state = GoalState(status="accepted", detail="Goal accepted", accepted=True)
            result_future = goal_handle.get_result_async()

            def _on_result(rf):
                res = rf.result()
                if res is None:
                    self.goal_state = GoalState(status="error", detail="No result", accepted=True)
                    return
                code = res.status
                if code == 4:
                    self.goal_state = GoalState(status="succeeded", detail="SUCCEEDED", accepted=True)
                elif code == 6:
                    self.goal_state = GoalState(status="aborted", detail="ABORTED", accepted=True)
                elif code == 5:
                    self.goal_state = GoalState(status="canceled", detail="CANCELED", accepted=True)
                else:
                    self.goal_state = GoalState(status="done", detail=f"status={code}", accepted=True)

            result_future.add_done_callback(_on_result)

        send_future.add_done_callback(_on_goal_response)


rclpy.init(args=None)
bridge = RosNav2Bridge()


def _spin_ros():
    rclpy.spin(bridge)


threading.Thread(target=_spin_ros, daemon=True).start()

app = FastAPI(title="web_nav2_ui")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/map")
def get_map():
    m = bridge.get_map()
    if m is None:
        raise HTTPException(status_code=404, detail="/map not received yet")
    return m


@app.get("/api/pose")
def get_pose():
    p = bridge.get_pose()
    if p is None:
        raise HTTPException(status_code=404, detail="/odom not received yet")
    return p


@app.post("/api/goal")
def post_goal(req: GoalRequest):
    try:
        bridge.send_goal(req.x, req.y, req.yaw_deg)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/goal/status")
def goal_status():
    return asdict(bridge.goal_state)


app.mount("/", StaticFiles(directory="/work/web_nav2_ui/frontend", html=True), name="frontend")
