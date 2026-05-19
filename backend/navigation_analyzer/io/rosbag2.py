from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from navigation_analyzer.models import AnalyzerConfig, Costmap, NavigationRun, NavigationSample, Point2D, Pose2D


@dataclass
class _PoseEvent:
    t: float
    pose: Pose2D


@dataclass
class _CmdEvent:
    t: float
    cmd_v: float
    cmd_w: float


@dataclass
class _DistanceEvent:
    t: float
    distance: float


@dataclass
class _TransformEvent:
    t: float
    parent: str
    child: str
    x: float
    y: float
    yaw: float
    stamp_t: float | None = None


def read_rosbag2(path: Path, config: AnalyzerConfig | None = None) -> NavigationRun:
    """Read a ROS2 bag into the canonical NavigationRun schema.

    The implementation uses dynamic ROS imports so the rest of the package can
    run in non-ROS CI environments. Source a ROS2 shell before calling this on
    a real bag.
    """

    resolved_config = config or AnalyzerConfig()
    rosbag2_py, deserialize_message, get_message = _load_ros_modules()

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id=_storage_id(path)),
        rosbag2_py.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    selected = _select_topics(topic_types, resolved_config)

    poses: list[_PoseEvent] = []
    localization_poses: list[_PoseEvent] = []
    map_poses: list[_PoseEvent] = []
    map_to_odom: list[_TransformEvent] = []
    odom_to_base: list[_TransformEvent] = []
    direct_map_to_base: list[_TransformEvent] = []
    cmds: list[_CmdEvent] = []
    distances: list[_DistanceEvent] = []
    recovery_times: list[float] = []
    planned_path: list[Point2D] = []
    planned_path_time: float | None = None
    planned_path_topic: str | None = None
    goal_pose: Pose2D | None = None
    goal_time: float | None = None
    costmap: Costmap | None = None
    route_summary: dict[str, Any] | None = None
    route_time: float | None = None
    route_topic: str | None = None
    start_ns: int | None = None
    message_counts: dict[str, int] = {}

    while reader.has_next():
        topic, data, timestamp_ns = reader.read_next()
        start_ns = timestamp_ns if start_ns is None else start_ns
        relative_t = (timestamp_ns - start_ns) / 1e9
        message_counts[topic] = message_counts.get(topic, 0) + 1

        if topic not in selected["all"]:
            continue

        msg_type = get_message(topic_types[topic])
        msg = deserialize_message(data, msg_type)
        t = relative_t

        if topic in selected["tf"]:
            transforms = _extract_transforms(msg, t, start_ns)
            for transform in transforms:
                parent = _norm_frame(transform.parent)
                child = _norm_frame(transform.child)
                if parent == "map" and child == "odom":
                    map_to_odom.append(transform)
                elif parent == "odom" and child in {"base_link", "base_footprint"}:
                    odom_to_base.append(transform)
                elif parent == "map" and child in {"base_link", "base_footprint"}:
                    direct_map_to_base.append(transform)
        elif topic in selected["localization_pose"]:
            pose = _extract_pose(msg)
            if pose is not None:
                localization_poses.append(_PoseEvent(t=t, pose=pose))
        elif topic in selected["odometry"]:
            pose = _extract_pose(msg)
            if pose is not None:
                poses.append(_PoseEvent(t=t, pose=pose))
        elif topic in selected["cmd_vel"]:
            cmd = _extract_cmd(msg)
            if cmd is not None:
                cmds.append(_CmdEvent(t=t, cmd_v=cmd[0], cmd_w=cmd[1]))
        elif topic in selected["scan"]:
            distance = _extract_scan_distance(msg)
            if distance is not None:
                distances.append(_DistanceEvent(t=t, distance=distance))
        elif topic in selected["pointcloud"]:
            distance = _extract_pointcloud_distance(msg)
            if distance is not None:
                distances.append(_DistanceEvent(t=t, distance=distance))
        elif topic in selected["plan"] or topic in selected["trajectory"] or topic in selected["route"]:
            if topic in selected["route"]:
                extracted_route = _extract_route_summary(msg)
                if extracted_route is not None:
                    route_summary = extracted_route
                    route_time = t
                    route_topic = topic
            path_points = _extract_path(msg)
            if path_points:
                planned_path = path_points
                planned_path_time = t
                planned_path_topic = topic
        elif topic in selected["costmap"]:
            extracted_costmap = _extract_costmap(msg)
            if extracted_costmap is not None:
                costmap = extracted_costmap
        elif topic in selected["goal"]:
            extracted_goal = _extract_pose(msg)
            if extracted_goal is not None:
                goal_pose = extracted_goal
                goal_time = t if goal_time is None else goal_time
        elif topic in selected["recovery"]:
            recovery_times.append(relative_t)

    map_poses = _build_map_poses(direct_map_to_base, map_to_odom, odom_to_base)
    pose_events = map_poses or localization_poses or poses
    if not pose_events:
        raise RuntimeError(
            "No localization or odometry poses were extracted from the ROS2 bag. "
            f"Available topics: {sorted(topic_types)}. "
            f"Configured pose topics: {resolved_config.rosbag_topics.localization_pose + resolved_config.rosbag_topics.odometry}."
        )

    goal_source = "goal_topic" if goal_pose is not None else None
    if goal_pose is None and route_summary is not None:
        route_goal = _pose2d_from_summary(route_summary.get("goal_pose"))
        if route_goal is not None:
            goal_pose = route_goal
            goal_time = route_time
            goal_source = "route_summary"

    sample_times = sorted({event.t for event in pose_events})
    tf_ages = compute_tf_ages_for_times(sample_times, map_to_odom, odom_to_base, direct_map_to_base)
    samples = _build_samples(pose_events, cmds, distances, recovery_times, goal_pose, tf_ages)
    if goal_time is not None:
        samples = [sample for sample in samples if sample.t >= goal_time]
    return NavigationRun(
        run_id=path.name,
        source=str(path),
        goal=Point2D(x=goal_pose.x, y=goal_pose.y) if goal_pose is not None else None,
        goal_pose=goal_pose,
        planned_path=planned_path,
        samples=samples,
        costmap=costmap,
        metadata={
            "reader": "rosbag2_py",
            "topic_types": topic_types,
            "selected_topics": {key: sorted(value) for key, value in selected.items() if key != "all"},
            "message_counts": message_counts,
            "goal_time": goal_time,
            "goal_source": goal_source,
            "planned_path_time": planned_path_time,
            "planned_path_topic": planned_path_topic,
            "route_time": route_time,
            "route_topic": route_topic,
            "route_summary": route_summary,
        },
    )


def _load_ros_modules():
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as exc:
        raise RuntimeError(
            "ROS2 bag reading requires rosbag2_py, rclpy, and rosidl_runtime_py. "
            "Source a ROS2 environment, or pass canonical JSON such as "
            "examples/sample_bag/sample_navigation.json."
        ) from exc
    return rosbag2_py, deserialize_message, get_message


def _storage_id(path: Path) -> str:
    metadata_path = path / "metadata.yaml" if path.is_dir() else path.with_name("metadata.yaml")
    if metadata_path.exists():
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
        storage_identifier = metadata.get("rosbag2_bagfile_information", {}).get("storage_identifier")
        if storage_identifier:
            return storage_identifier
    if any(path.glob("*.mcap")) if path.is_dir() else path.suffix == ".mcap":
        return "mcap"
    return "sqlite3"


def _select_topics(topic_types: dict[str, str], config: AnalyzerConfig) -> dict[str, set[str]]:
    configured = config.rosbag_topics
    selected = {
        "tf": {topic for topic in configured.tf if topic in topic_types},
        "odometry": _match(topic_types, configured.odometry, {"nav_msgs/msg/Odometry"}),
        "localization_pose": _match(
            topic_types,
            configured.localization_pose,
            {"geometry_msgs/msg/PoseWithCovarianceStamped", "geometry_msgs/msg/PoseStamped"},
        ),
        "cmd_vel": _match(
            topic_types,
            configured.cmd_vel,
            {
                "geometry_msgs/msg/Twist",
                "geometry_msgs/msg/TwistStamped",
                "autoware_control_msgs/msg/Control",
                "autoware_control_msgs/msg/ControlCommand",
            },
        ),
        "scan": _match(topic_types, configured.scan, {"sensor_msgs/msg/LaserScan"}),
        "pointcloud": _match(topic_types, configured.pointcloud, {"sensor_msgs/msg/PointCloud2"}),
        "plan": _match(topic_types, configured.plan, {"nav_msgs/msg/Path", "autoware_planning_msgs/msg/Trajectory"}),
        "trajectory": _match(topic_types, configured.trajectory, {"nav_msgs/msg/Path", "autoware_planning_msgs/msg/Trajectory"}),
        "route": _match(topic_types, configured.plan + configured.trajectory, {"autoware_planning_msgs/msg/LaneletRoute"}),
        "costmap": _match(topic_types, configured.costmap, {"nav_msgs/msg/OccupancyGrid"}),
        "goal": _match(topic_types, configured.goal, {"geometry_msgs/msg/PoseStamped", "geometry_msgs/msg/PoseWithCovarianceStamped"}),
        "recovery": {topic for topic in configured.recovery if topic in topic_types},
    }
    selected["all"] = set().union(*selected.values())
    return selected


def _match(topic_types: dict[str, str], preferred_names: list[str], message_types: set[str]) -> set[str]:
    matches = {topic for topic in preferred_names if topic in topic_types}
    if matches:
        return matches
    return {topic for topic, message_type in topic_types.items() if message_type in message_types}


def _extract_pose(msg: Any) -> Pose2D | None:
    pose = getattr(msg, "pose", None)
    if pose is None:
        return None
    pose = getattr(pose, "pose", pose)
    position = getattr(pose, "position", None)
    orientation = getattr(pose, "orientation", None)
    if position is None:
        return None
    return Pose2D(
        x=float(position.x),
        y=float(position.y),
        yaw=_yaw_from_quaternion(orientation) if orientation is not None else 0.0,
    )


def _extract_cmd(msg: Any) -> tuple[float, float] | None:
    control = getattr(msg, "lateral", None)
    longitudinal = getattr(msg, "longitudinal", None)
    if control is not None or longitudinal is not None:
        velocity = float(getattr(longitudinal, "velocity", getattr(longitudinal, "speed", 0.0))) if longitudinal is not None else 0.0
        steering = float(getattr(control, "steering_tire_angle", 0.0)) if control is not None else 0.0
        return velocity, steering

    twist = getattr(msg, "twist", msg)
    linear = getattr(twist, "linear", None)
    angular = getattr(twist, "angular", None)
    if linear is None or angular is None:
        return None
    return float(getattr(linear, "x", 0.0)), float(getattr(angular, "z", 0.0))


def _extract_transforms(msg: Any, t: float, start_ns: int | None) -> list[_TransformEvent]:
    transforms = []
    for transform in getattr(msg, "transforms", []):
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        stamp_t = _stamp_to_relative(getattr(transform.header, "stamp", None), start_ns)
        transforms.append(
            _TransformEvent(
                t=t,
                parent=str(transform.header.frame_id),
                child=str(transform.child_frame_id),
                x=float(translation.x),
                y=float(translation.y),
                yaw=_yaw_from_quaternion(rotation),
                stamp_t=stamp_t,
            )
        )
    return transforms


def _stamp_to_relative(stamp: Any, start_ns: int | None) -> float | None:
    if stamp is None or start_ns is None:
        return None
    sec = getattr(stamp, "sec", None)
    nanosec = getattr(stamp, "nanosec", None)
    if sec is None or nanosec is None:
        return None
    stamp_ns = int(sec) * 1_000_000_000 + int(nanosec)
    if stamp_ns == 0:
        return None
    return (stamp_ns - start_ns) / 1e9


def _extract_scan_distance(msg: Any) -> float | None:
    ranges = getattr(msg, "ranges", None)
    if ranges is None:
        return None
    finite = [float(value) for value in ranges if math.isfinite(float(value)) and float(value) > 0.0]
    return min(finite) if finite else None


def _extract_pointcloud_distance(msg: Any) -> float | None:
    try:
        from sensor_msgs_py import point_cloud2
    except ImportError:
        return None
    distances = []
    for index, point in enumerate(point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)):
        if index >= 20000:
            break
        x, y, z = float(point[0]), float(point[1]), float(point[2])
        distances.append(math.sqrt(x * x + y * y + z * z))
    return min(distances) if distances else None


def _extract_path(msg: Any) -> list[Point2D]:
    poses = getattr(msg, "poses", None)
    if poses is None:
        poses = getattr(msg, "points", None)
    if poses is None:
        return []
    points = []
    for pose_stamped in poses:
        point = _extract_point(pose_stamped)
        if point is not None:
            points.append(point)
    return points


def _extract_route_summary(msg: Any) -> dict[str, Any] | None:
    segments = getattr(msg, "segments", None)
    if segments is None:
        return None
    primitive_ids: list[int] = []
    preferred_ids: list[int] = []
    primitive_types: dict[str, int] = {}
    segment_summaries = []
    for segment in segments:
        preferred = getattr(segment, "preferred_primitive", None)
        preferred_id = int(getattr(preferred, "id", 0)) if preferred is not None else None
        preferred_type = str(getattr(preferred, "primitive_type", "")) if preferred is not None else ""
        if preferred_id is not None:
            preferred_ids.append(preferred_id)
        primitives = []
        for primitive in getattr(segment, "primitives", []):
            primitive_id = int(getattr(primitive, "id", 0))
            primitive_type = str(getattr(primitive, "primitive_type", ""))
            primitive_ids.append(primitive_id)
            primitive_types[primitive_type] = primitive_types.get(primitive_type, 0) + 1
            primitives.append({"id": primitive_id, "type": primitive_type})
        segment_summaries.append(
            {
                "preferred_id": preferred_id,
                "preferred_type": preferred_type,
                "primitive_count": len(primitives),
                "primitive_ids": [primitive["id"] for primitive in primitives[:12]],
            }
        )
    start_pose = _pose_summary(getattr(msg, "start_pose", None))
    goal_pose = _pose_summary(getattr(msg, "goal_pose", None))
    return {
        "segment_count": len(segments),
        "primitive_count": len(primitive_ids),
        "unique_primitive_count": len(set(primitive_ids)),
        "preferred_ids": preferred_ids,
        "primitive_ids": primitive_ids[:200],
        "primitive_types": primitive_types,
        "segments": segment_summaries[:50],
        "start_pose": start_pose,
        "goal_pose": goal_pose,
        "uuid": _uuid_summary(getattr(msg, "uuid", None)),
        "allow_modification": bool(getattr(msg, "allow_modification", False)),
    }


def _pose_summary(pose: Any) -> dict[str, float] | None:
    if pose is None:
        return None
    position = getattr(pose, "position", None)
    orientation = getattr(pose, "orientation", None)
    if position is None:
        return None
    return {
        "x": float(getattr(position, "x", 0.0)),
        "y": float(getattr(position, "y", 0.0)),
        "z": float(getattr(position, "z", 0.0)),
        "yaw": _yaw_from_quaternion(orientation) if orientation is not None else 0.0,
    }


def _pose2d_from_summary(summary: Any) -> Pose2D | None:
    if not isinstance(summary, dict):
        return None
    x = summary.get("x")
    y = summary.get("y")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        return None
    yaw = summary.get("yaw", 0.0)
    return Pose2D(x=float(x), y=float(y), yaw=float(yaw) if isinstance(yaw, int | float) else 0.0)


def _uuid_summary(uuid_msg: Any) -> str | None:
    raw = getattr(uuid_msg, "uuid", None)
    if raw is None:
        return None
    values = [int(value) for value in raw]
    hexed = "".join(f"{value:02x}" for value in values)
    if len(hexed) != 32:
        return hexed
    return f"{hexed[:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:]}"


def _extract_costmap(msg: Any) -> Costmap | None:
    info = getattr(msg, "info", None)
    if info is None:
        return None
    origin_pose = getattr(info, "origin", None)
    origin_position = getattr(origin_pose, "position", None)
    origin = Point2D(
        x=float(getattr(origin_position, "x", 0.0)),
        y=float(getattr(origin_position, "y", 0.0)),
    )
    return Costmap(
        width=int(info.width),
        height=int(info.height),
        resolution=float(info.resolution),
        origin=origin,
        data=[float(value) for value in getattr(msg, "data", [])],
    )


def _extract_point(msg: Any) -> Point2D | None:
    pose = getattr(msg, "pose", msg)
    pose = getattr(pose, "pose", pose)
    position = getattr(pose, "position", None)
    if position is None:
        return None
    return Point2D(x=float(position.x), y=float(position.y))


def _build_samples(
    poses: list[_PoseEvent],
    cmds: list[_CmdEvent],
    distances: list[_DistanceEvent],
    recovery_times: list[float],
    goal: Point2D | None,
    tf_ages: dict[float, float | None] | None = None,
) -> list[NavigationSample]:
    samples = []
    for pose_event in sorted(poses, key=lambda event: event.t):
        cmd = _nearest(cmds, pose_event.t)
        distance = _nearest(distances, pose_event.t)
        samples.append(
            NavigationSample(
                t=pose_event.t,
                pose=pose_event.pose,
                cmd_v=cmd.cmd_v if cmd is not None else 0.0,
                cmd_w=cmd.cmd_w if cmd is not None else 0.0,
                goal_distance=_distance(pose_event.pose, goal) if goal is not None else None,
                obstacle_distance=distance.distance if distance is not None else None,
                collision=False,
                recovery_event=any(abs(pose_event.t - recovery_t) <= 0.25 for recovery_t in recovery_times),
                tf_age_s=tf_ages.get(pose_event.t) if tf_ages else None,
            )
        )
    return samples


def compute_tf_ages_for_times(
    sample_times: list[float],
    map_to_odom: list[_TransformEvent],
    odom_to_base: list[_TransformEvent],
    direct_map_to_base: list[_TransformEvent],
) -> dict[float, float | None]:
    """Compute the TF chain age at each sample time.

    Chain age at sample time T is T - min(latest stamp_t of each chain link at-or-before T).
    Returns None for samples that have no usable TF stamps before them.
    """

    direct_stamps = sorted(t.stamp_t for t in direct_map_to_base if t.stamp_t is not None)
    mo_stamps = sorted(t.stamp_t for t in map_to_odom if t.stamp_t is not None)
    ob_stamps = sorted(t.stamp_t for t in odom_to_base if t.stamp_t is not None)

    use_direct = bool(direct_stamps) and not (mo_stamps and ob_stamps)
    ages: dict[float, float | None] = {}
    for sample_t in sample_times:
        if use_direct:
            latest = _latest_at_or_before(direct_stamps, sample_t)
            ages[sample_t] = None if latest is None else max(0.0, sample_t - latest)
            continue
        latest_mo = _latest_at_or_before(mo_stamps, sample_t)
        latest_ob = _latest_at_or_before(ob_stamps, sample_t)
        if latest_mo is None or latest_ob is None:
            ages[sample_t] = None
            continue
        ages[sample_t] = max(0.0, sample_t - min(latest_mo, latest_ob))
    return ages


def _latest_at_or_before(sorted_stamps: list[float], reference: float) -> float | None:
    if not sorted_stamps:
        return None
    latest: float | None = None
    for stamp in sorted_stamps:
        if stamp > reference:
            break
        latest = stamp
    return latest


def _build_map_poses(
    direct_map_to_base: list[_TransformEvent],
    map_to_odom: list[_TransformEvent],
    odom_to_base: list[_TransformEvent],
) -> list[_PoseEvent]:
    if direct_map_to_base:
        return [_PoseEvent(t=event.t, pose=Pose2D(x=event.x, y=event.y, yaw=event.yaw)) for event in direct_map_to_base]
    if not map_to_odom or not odom_to_base:
        return []
    map_to_odom_sorted = sorted(map_to_odom, key=lambda event: event.t)
    poses = []
    for odom_base in sorted(odom_to_base, key=lambda event: event.t):
        map_odom = _nearest(map_to_odom_sorted, odom_base.t)
        if map_odom is None or abs(map_odom.t - odom_base.t) > 1.0:
            continue
        composed = _compose_transform(map_odom, odom_base)
        poses.append(_PoseEvent(t=odom_base.t, pose=Pose2D(x=composed.x, y=composed.y, yaw=composed.yaw)))
    return poses


def _compose_transform(a: _TransformEvent, b: _TransformEvent) -> _TransformEvent:
    cos_yaw = math.cos(a.yaw)
    sin_yaw = math.sin(a.yaw)
    x = a.x + cos_yaw * b.x - sin_yaw * b.y
    y = a.y + sin_yaw * b.x + cos_yaw * b.y
    return _TransformEvent(
        t=b.t,
        parent=a.parent,
        child=b.child,
        x=x,
        y=y,
        yaw=_normalize_angle(a.yaw + b.yaw),
    )


def _nearest(events: list[Any], t: float) -> Any | None:
    if not events:
        return None
    return min(events, key=lambda event: abs(event.t - t))


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _norm_frame(frame: str) -> str:
    return frame.lstrip("/")


def _normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _yaw_from_quaternion(q: Any) -> float:
    x = float(getattr(q, "x", 0.0))
    y = float(getattr(q, "y", 0.0))
    z = float(getattr(q, "z", 0.0))
    w = float(getattr(q, "w", 1.0))
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)
