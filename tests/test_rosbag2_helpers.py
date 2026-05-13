from types import SimpleNamespace

import pytest

from navigation_analyzer.io.rosbag2 import (
    _TransformEvent,
    _build_map_poses,
    _build_samples,
    _extract_cmd,
    _extract_path,
    _extract_route_summary,
    _pose2d_from_summary,
    _yaw_from_quaternion,
)
from navigation_analyzer.models import Point2D, Pose2D


def test_yaw_from_quaternion_z_90deg():
    q = SimpleNamespace(x=0.0, y=0.0, z=0.70710678, w=0.70710678)
    assert 1.56 < _yaw_from_quaternion(q) < 1.58


def test_build_samples_joins_nearest_cmd_and_distance():
    pose_event = SimpleNamespace(t=10.0, pose=Pose2D(x=1.0, y=2.0, yaw=0.0))
    cmd_event = SimpleNamespace(t=10.1, cmd_v=0.2, cmd_w=-0.3)
    distance_event = SimpleNamespace(t=9.9, distance=0.42)
    samples = _build_samples([pose_event], [cmd_event], [distance_event], [10.05], Point2D(x=2.0, y=2.0))

    assert len(samples) == 1
    assert samples[0].cmd_v == 0.2
    assert samples[0].cmd_w == -0.3
    assert samples[0].obstacle_distance == 0.42
    assert samples[0].goal_distance == 1.0
    assert samples[0].recovery_event is True


def test_build_map_poses_composes_map_odom_and_odom_base():
    map_to_odom = [_TransformEvent(t=1.0, parent="map", child="odom", x=1.0, y=2.0, yaw=0.0)]
    odom_to_base = [_TransformEvent(t=1.1, parent="odom", child="base_footprint", x=0.5, y=-0.25, yaw=0.1)]
    poses = _build_map_poses([], map_to_odom, odom_to_base)

    assert len(poses) == 1
    assert poses[0].pose.x == 1.5
    assert poses[0].pose.y == 1.75
    assert poses[0].pose.yaw == pytest.approx(0.1)


def test_autoware_control_command_extraction():
    msg = SimpleNamespace(
        lateral=SimpleNamespace(steering_tire_angle=0.12),
        longitudinal=SimpleNamespace(velocity=2.4),
    )

    assert _extract_cmd(msg) == (2.4, 0.12)


def test_autoware_trajectory_path_extraction():
    msg = SimpleNamespace(
        points=[
            SimpleNamespace(pose=SimpleNamespace(position=SimpleNamespace(x=1.0, y=2.0))),
            SimpleNamespace(pose=SimpleNamespace(position=SimpleNamespace(x=3.0, y=4.0))),
        ]
    )

    points = _extract_path(msg)

    assert [(point.x, point.y) for point in points] == [(1.0, 2.0), (3.0, 4.0)]


def test_autoware_lanelet_route_summary_extraction():
    route = SimpleNamespace(
        start_pose=SimpleNamespace(
            position=SimpleNamespace(x=1.0, y=2.0, z=3.0),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
        ),
        goal_pose=SimpleNamespace(
            position=SimpleNamespace(x=4.0, y=5.0, z=6.0),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
        ),
        segments=[
            SimpleNamespace(
                preferred_primitive=SimpleNamespace(id=127, primitive_type="lane"),
                primitives=[
                    SimpleNamespace(id=127, primitive_type="lane"),
                    SimpleNamespace(id=128, primitive_type="lane"),
                ],
            )
        ],
        uuid=SimpleNamespace(uuid=[0] * 16),
        allow_modification=True,
    )

    summary = _extract_route_summary(route)

    assert summary is not None
    assert summary["segment_count"] == 1
    assert summary["primitive_count"] == 2
    assert summary["unique_primitive_count"] == 2
    assert summary["preferred_ids"] == [127]
    assert summary["primitive_types"] == {"lane": 2}
    assert summary["start_pose"]["x"] == 1.0
    assert summary["goal_pose"]["y"] == 5.0


def test_route_goal_summary_converts_to_pose2d():
    pose = _pose2d_from_summary({"x": 4.0, "y": 5.0, "z": 6.0, "yaw": 0.7})

    assert pose == Pose2D(x=4.0, y=5.0, yaw=0.7)
