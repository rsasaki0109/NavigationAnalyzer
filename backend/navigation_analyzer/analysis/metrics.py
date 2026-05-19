from __future__ import annotations

import math
from collections.abc import Iterable

from navigation_analyzer.analysis.lanelet2 import compute_route_lanelet_metrics
from navigation_analyzer.models import AnalyzerConfig, MetricResult, NavigationRun, Point2D


def compute_metrics(run: NavigationRun, config: AnalyzerConfig) -> dict[str, MetricResult]:
    samples = sorted(run.samples, key=lambda sample: sample.t)
    final_goal_distance = _final_goal_distance(run)
    time_to_goal = _time_to_goal(samples, config.goal_tolerance_m)
    path_length = _path_length([sample.pose for sample in samples])
    collision_count = _collision_count(run, config)
    oscillation_count = _oscillation_count(samples)
    recovery_count = sum(1 for sample in samples if sample.recovery_event)
    minimum_obstacle_distance = _minimum_obstacle_distance(run)
    final_goal_errors = _final_goal_errors(run)
    route_line_errors = _route_line_errors(run)
    route_lanelet_metrics = compute_route_lanelet_metrics(run, config.lanelet2_map)
    stopped_duration = _final_stopped_duration(samples, stopped_velocity=0.05)
    tf_health = _tf_health(samples)

    return {
        "success_rate": MetricResult(
            name="success_rate",
            value=1.0 if final_goal_distance is not None and final_goal_distance <= config.goal_tolerance_m else 0.0,
            unit="ratio",
            description="Run-level success encoded as 1.0 or 0.0 for benchmark aggregation.",
        ),
        "path_length": MetricResult(
            name="path_length",
            value=path_length,
            unit="m",
            description="Integrated trajectory length from odometry poses.",
        ),
        "goal_distance": MetricResult(
            name="goal_distance",
            value=final_goal_distance,
            unit="m",
            description="Final distance to the navigation goal.",
        ),
        "time_to_goal": MetricResult(
            name="time_to_goal",
            value=time_to_goal,
            unit="s",
            description="First timestamp where goal tolerance was reached.",
        ),
        "collision_count": MetricResult(
            name="collision_count",
            value=collision_count,
            unit="count",
            description="Collision events inferred from flags or obstacle distance threshold crossings.",
        ),
        "oscillation_count": MetricResult(
            name="oscillation_count",
            value=oscillation_count,
            unit="count",
            description="Angular velocity sign changes while commanded motion is active.",
        ),
        "recovery_count": MetricResult(
            name="recovery_count",
            value=recovery_count,
            unit="count",
            description="Recovery behavior events from run samples.",
        ),
        "path_smoothness": MetricResult(
            name="path_smoothness",
            value=_path_smoothness([sample.pose for sample in samples]),
            unit="rad/m",
            description="Mean absolute heading change per meter; lower is smoother.",
        ),
        "minimum_obstacle_distance": MetricResult(
            name="minimum_obstacle_distance",
            value=minimum_obstacle_distance,
            unit="m",
            description="Minimum observed obstacle clearance.",
        ),
        "final_lateral_error": MetricResult(
            name="final_lateral_error",
            value=final_goal_errors["lateral"],
            unit="m",
            description="Final cross-track error in the goal frame; positive is left of goal heading.",
        ),
        "final_longitudinal_error": MetricResult(
            name="final_longitudinal_error",
            value=final_goal_errors["longitudinal"],
            unit="m",
            description="Final along-track error in the goal frame; positive is past the goal heading direction.",
        ),
        "final_yaw_error": MetricResult(
            name="final_yaw_error",
            value=final_goal_errors["yaw"],
            unit="rad",
            description="Final heading error relative to goal yaw.",
        ),
        "final_stopped_duration": MetricResult(
            name="final_stopped_duration",
            value=stopped_duration,
            unit="s",
            description="Duration at the end of the run where commanded linear and angular speeds are near zero.",
        ),
        "route_progress_ratio": MetricResult(
            name="route_progress_ratio",
            value=route_line_errors["progress_ratio"],
            unit="ratio",
            description="Final progress projected onto the Autoware route start-to-goal line; 0 is route start and 1 is route goal.",
        ),
        "route_straight_line_lateral_error": MetricResult(
            name="route_straight_line_lateral_error",
            value=route_line_errors["lateral"],
            unit="m",
            description="Final signed lateral offset from the Autoware route start-to-goal line; positive is left of route direction.",
        ),
        "route_straight_line_remaining_distance": MetricResult(
            name="route_straight_line_remaining_distance",
            value=route_line_errors["remaining"],
            unit="m",
            description="Remaining distance along the Autoware route start-to-goal line after projecting the final pose.",
        ),
        "route_lanelet_centerline_distance": MetricResult(
            name="route_lanelet_centerline_distance",
            value=route_lanelet_metrics["final_centerline_distance"],
            unit="m",
            description="Final distance to the preferred Autoware route lanelet centerline from the lanelet2 map.",
        ),
        "route_lanelet_mean_centerline_distance": MetricResult(
            name="route_lanelet_mean_centerline_distance",
            value=route_lanelet_metrics["mean_centerline_distance"],
            unit="m",
            description="Mean distance from pose samples to the preferred Autoware route lanelet centerline.",
        ),
        "route_lanelet_max_centerline_distance": MetricResult(
            name="route_lanelet_max_centerline_distance",
            value=route_lanelet_metrics["max_centerline_distance"],
            unit="m",
            description="Maximum distance from pose samples to the preferred Autoware route lanelet centerline.",
        ),
        "route_lanelet_progress_ratio": MetricResult(
            name="route_lanelet_progress_ratio",
            value=route_lanelet_metrics["progress_ratio"],
            unit="ratio",
            description="Final progress projected onto the preferred Autoware route lanelet centerline.",
        ),
        "route_lanelet_remaining_distance": MetricResult(
            name="route_lanelet_remaining_distance",
            value=route_lanelet_metrics["remaining_distance"],
            unit="m",
            description="Remaining distance along the preferred Autoware route lanelet centerline after final pose projection.",
        ),
        "route_lanelet_matched_count": MetricResult(
            name="route_lanelet_matched_count",
            value=route_lanelet_metrics["matched_lanelet_count"],
            unit="count",
            description="Number of preferred route lanelets found in the configured lanelet2 map.",
        ),
        "tf_max_age_s": MetricResult(
            name="tf_max_age_s",
            value=tf_health["max_age_s"],
            unit="s",
            description="Maximum observed TF chain age across samples (None when no sample carries tf_age_s).",
        ),
        "tf_mean_age_s": MetricResult(
            name="tf_mean_age_s",
            value=tf_health["mean_age_s"],
            unit="s",
            description="Mean TF chain age across samples that report tf_age_s.",
        ),
        "tf_health_sample_coverage": MetricResult(
            name="tf_health_sample_coverage",
            value=tf_health["coverage"],
            unit="ratio",
            description="Fraction of samples that carry a tf_age_s reading.",
        ),
    }


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _path_length(points: Iterable[Point2D]) -> float:
    total = 0.0
    previous: Point2D | None = None
    for point in points:
        if previous is not None:
            total += _distance(previous, point)
        previous = point
    return total


def _final_goal_distance(run: NavigationRun) -> float | None:
    if not run.samples:
        return None
    last = run.samples[-1]
    if last.goal_distance is not None:
        return last.goal_distance
    goal = _goal_point(run)
    if goal is None:
        return None
    return _distance(last.pose, goal)


def _time_to_goal(samples, goal_tolerance_m: float) -> float | None:
    if not samples:
        return None
    start_t = samples[0].t
    for sample in samples:
        if sample.goal_distance is not None and sample.goal_distance <= goal_tolerance_m:
            return sample.t - start_t
    return None


def _tf_health(samples) -> dict[str, float | None]:
    ages = [sample.tf_age_s for sample in samples if sample.tf_age_s is not None]
    if not samples:
        return {"max_age_s": None, "mean_age_s": None, "coverage": None}
    coverage = len(ages) / len(samples) if samples else 0.0
    if not ages:
        return {"max_age_s": None, "mean_age_s": None, "coverage": coverage}
    return {
        "max_age_s": max(ages),
        "mean_age_s": sum(ages) / len(ages),
        "coverage": coverage,
    }


def _collision_count(run: NavigationRun, config: AnalyzerConfig) -> int:
    count = 0
    in_collision = False
    for sample in run.samples:
        collided = sample.collision or (
            sample.obstacle_distance is not None and sample.obstacle_distance <= config.collision_distance_m
        )
        if collided and not in_collision:
            count += 1
        in_collision = collided
    return count


def _oscillation_count(samples) -> int:
    count = 0
    previous_sign = 0
    for sample in samples:
        if abs(sample.cmd_w) < 0.05 or abs(sample.cmd_v) > 0.08:
            continue
        sign = 1 if sample.cmd_w > 0 else -1
        if previous_sign and sign != previous_sign:
            count += 1
        previous_sign = sign
    return count


def _path_smoothness(points: list[Point2D]) -> float | None:
    filtered = _movement_filtered(points)
    if len(filtered) < 3:
        return None
    heading_change = 0.0
    length = _path_length(filtered)
    for a, b, c in zip(filtered, filtered[1:], filtered[2:]):
        h1 = math.atan2(b.y - a.y, b.x - a.x)
        h2 = math.atan2(c.y - b.y, c.x - b.x)
        heading_change += abs(math.atan2(math.sin(h2 - h1), math.cos(h2 - h1)))
    return heading_change / max(length, 1e-6)


def _movement_filtered(points: list[Point2D], min_step_m: float = 0.03) -> list[Point2D]:
    if not points:
        return []
    filtered = [points[0]]
    for point in points[1:]:
        if _distance(filtered[-1], point) >= min_step_m:
            filtered.append(point)
    if filtered[-1] is not points[-1]:
        filtered.append(points[-1])
    return filtered


def _minimum_obstacle_distance(run: NavigationRun) -> float | None:
    values = [sample.obstacle_distance for sample in run.samples if sample.obstacle_distance is not None]
    return min(values) if values else None


def _final_goal_errors(run: NavigationRun) -> dict[str, float | None]:
    if not run.samples or run.goal_pose is None:
        return {"lateral": None, "longitudinal": None, "yaw": None}
    final_pose = run.samples[-1].pose
    goal = run.goal_pose
    dx = final_pose.x - goal.x
    dy = final_pose.y - goal.y
    cos_yaw = math.cos(goal.yaw)
    sin_yaw = math.sin(goal.yaw)
    longitudinal = cos_yaw * dx + sin_yaw * dy
    lateral = -sin_yaw * dx + cos_yaw * dy
    yaw_error = _angle_diff(final_pose.yaw, goal.yaw)
    return {"lateral": lateral, "longitudinal": longitudinal, "yaw": yaw_error}


def _route_line_errors(run: NavigationRun) -> dict[str, float | None]:
    route_summary = run.metadata.get("route_summary")
    if not run.samples or not isinstance(route_summary, dict):
        return {"progress_ratio": None, "lateral": None, "remaining": None}
    start = _point_from_route_pose(route_summary.get("start_pose"))
    goal = _point_from_route_pose(route_summary.get("goal_pose"))
    if start is None or goal is None:
        return {"progress_ratio": None, "lateral": None, "remaining": None}

    dx = goal.x - start.x
    dy = goal.y - start.y
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return {"progress_ratio": None, "lateral": None, "remaining": None}

    final_pose = run.samples[-1].pose
    fx = final_pose.x - start.x
    fy = final_pose.y - start.y
    along = (fx * dx + fy * dy) / length
    lateral = (dx * fy - dy * fx) / length
    progress = max(0.0, min(1.0, along / length))
    remaining = max(0.0, length - along)
    return {"progress_ratio": progress, "lateral": lateral, "remaining": remaining}


def _point_from_route_pose(value) -> Point2D | None:
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        return None
    return Point2D(x=float(x), y=float(y))


def _final_stopped_duration(samples, stopped_velocity: float) -> float:
    if not samples:
        return 0.0
    last_t = samples[-1].t
    stopped_since = last_t
    for sample in reversed(samples):
        if abs(sample.cmd_v) + abs(sample.cmd_w) > stopped_velocity:
            break
        stopped_since = sample.t
    return max(0.0, last_t - stopped_since)


def _goal_point(run: NavigationRun) -> Point2D | None:
    if run.goal_pose is not None:
        return run.goal_pose
    return run.goal


def _angle_diff(a: float, b: float) -> float:
    return math.atan2(math.sin(a - b), math.cos(a - b))
