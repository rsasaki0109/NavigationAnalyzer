#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import time

import rclpy
from autoware_adapi_v1_msgs.srv import ChangeOperationMode, InitializeLocalization, SetRoutePoints
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tier4_external_api_msgs.srv import Engage


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive Autoware planning simulator without RViz.")
    parser.add_argument("--initial", nargs=4, type=float, metavar=("X", "Y", "Z", "YAW"), required=True)
    parser.add_argument("--goal", nargs=4, type=float, metavar=("X", "Y", "Z", "YAW"), required=True)
    parser.add_argument("--wait-after-engage", type=float, default=30.0)
    args = parser.parse_args()

    rclpy.init()
    node = Node("navigation_analyzer_autoware_drive_goal")
    driver = _AutowareDriver(node)
    try:
        driver.wait_ready()
        driver.publish_initial_pose(args.initial)
        driver.wait_for_odom()
        driver.publish_goal_topic(args.goal)
        route_ok = driver.set_route(args.goal)
        if not route_ok:
            return 3
        driver.change_to_autonomous()
        driver.engage()
        driver.spin_for(args.wait_after_engage)
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


class _AutowareDriver:
    def __init__(self, node: Node) -> None:
        self.node = node
        self.last_odom: Odometry | None = None
        self.initial_pub = node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        self.initial_3d_pub = node.create_publisher(PoseWithCovarianceStamped, "/initialpose3d", 10)
        self.goal_pub = node.create_publisher(PoseStamped, "/planning/mission_planning/goal", 10)
        self.route_client = node.create_client(SetRoutePoints, "/api/routing/set_route_points")
        self.localization_client = node.create_client(InitializeLocalization, "/api/localization/initialize")
        self.autonomous_client = node.create_client(ChangeOperationMode, "/api/operation_mode/change_to_autonomous")
        self.engage_client = node.create_client(Engage, "/api/autoware/set/engage")
        node.create_subscription(Odometry, "/localization/kinematic_state", self._on_odom, 10)

    def _on_odom(self, msg: Odometry) -> None:
        self.last_odom = msg

    def wait_ready(self) -> None:
        for name, client in [
            ("set_route_points", self.route_client),
            ("initialize_localization", self.localization_client),
            ("change_to_autonomous", self.autonomous_client),
            ("engage", self.engage_client),
        ]:
            if not client.wait_for_service(timeout_sec=20.0):
                raise RuntimeError(f"Timed out waiting for service: {name}")
        self._spin_until(
            lambda: self.initial_pub.get_subscription_count() > 0 or self.initial_3d_pub.get_subscription_count() > 0,
            20.0,
            "initial pose subscriber",
        )

    def publish_initial_pose(self, pose: list[float]) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = pose[0]
        msg.pose.pose.position.y = pose[1]
        msg.pose.pose.position.z = pose[2]
        _set_yaw(msg.pose.pose.orientation, pose[3])
        covariance = [0.0] * 36
        covariance[0] = 0.25
        covariance[7] = 0.25
        covariance[14] = 0.25
        covariance[35] = 0.0685
        msg.pose.covariance = covariance
        for _ in range(8):
            msg.header.stamp = self.node.get_clock().now().to_msg()
            self.initial_pub.publish(msg)
            self.initial_3d_pub.publish(msg)
            self.spin_for(0.25)
        request = InitializeLocalization.Request()
        request.pose.append(msg)
        future = self.localization_client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=20.0)
        response = future.result()
        print(f"initialize: {response}", flush=True)

    def publish_goal_topic(self, pose: list[float]) -> None:
        msg = PoseStamped()
        msg.header.frame_id = "map"
        msg.pose.position.x = pose[0]
        msg.pose.position.y = pose[1]
        msg.pose.position.z = pose[2]
        _set_yaw(msg.pose.orientation, pose[3])
        for _ in range(3):
            msg.header.stamp = self.node.get_clock().now().to_msg()
            self.goal_pub.publish(msg)
            self.spin_for(0.2)

    def wait_for_odom(self) -> None:
        self._spin_until(lambda: self.last_odom is not None, 20.0, "localization odometry")
        pose = self.last_odom.pose.pose.position if self.last_odom is not None else None
        if pose is not None:
            print(f"odom: x={pose.x:.3f} y={pose.y:.3f} z={pose.z:.3f}", flush=True)

    def set_route(self, pose: list[float]) -> bool:
        request = SetRoutePoints.Request()
        request.header.frame_id = "map"
        request.header.stamp = self.node.get_clock().now().to_msg()
        request.option.allow_goal_modification = True
        request.goal.position.x = pose[0]
        request.goal.position.y = pose[1]
        request.goal.position.z = pose[2]
        _set_yaw(request.goal.orientation, pose[3])
        future = self.route_client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=20.0)
        response = future.result()
        if response is None:
            print("route: timeout", flush=True)
            return False
        print(
            f"route: success={response.status.success} code={response.status.code} message={response.status.message!r}",
            flush=True,
        )
        return bool(response.status.success)

    def change_to_autonomous(self) -> None:
        future = self.autonomous_client.call_async(ChangeOperationMode.Request())
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=10.0)
        response = future.result()
        print(f"autonomous: {response}", flush=True)

    def engage(self) -> None:
        request = Engage.Request()
        request.engage = True
        future = self.engage_client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=10.0)
        response = future.result()
        print(f"engage: {response}", flush=True)

    def spin_for(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def _spin_until(self, predicate, timeout: float, label: str) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if predicate():
                return
        raise RuntimeError(f"Timed out waiting for {label}")


def _set_yaw(orientation, yaw: float) -> None:
    orientation.z = math.sin(yaw / 2.0)
    orientation.w = math.cos(yaw / 2.0)


if __name__ == "__main__":
    raise SystemExit(main())
