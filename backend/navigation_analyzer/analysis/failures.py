from __future__ import annotations

import math

from navigation_analyzer.models import AnalyzerConfig, FailureFinding, NavigationRun, Point2D, Severity


def detect_failures(run: NavigationRun, config: AnalyzerConfig) -> list[FailureFinding]:
    findings: list[FailureFinding] = []
    samples = sorted(run.samples, key=lambda sample: sample.t)
    if not samples:
        return findings

    findings.extend(_localization_drift(samples, config))
    findings.extend(_oscillation(samples, config))
    findings.extend(_deadlock(samples, config))
    findings.extend(_narrow_passage(samples, config))
    findings.extend(_dynamic_obstacle_freeze(samples))
    findings.extend(_planner_divergence(run, config))
    return sorted(findings, key=lambda finding: finding.timestamp)


def _localization_drift(samples, config: AnalyzerConfig) -> list[FailureFinding]:
    drift_samples = [
        sample for sample in samples
        if sample.localization_error is not None and sample.localization_error >= config.localization_drift_m
    ]
    if not drift_samples:
        return []
    worst = max(drift_samples, key=lambda sample: sample.localization_error or 0.0)
    return [
        FailureFinding(
            failure_type="localization_drift",
            timestamp=worst.t,
            severity=Severity.high if (worst.localization_error or 0.0) > config.localization_drift_m * 1.5 else Severity.medium,
            confidence=0.82,
            evidence={"localization_error_m": worst.localization_error},
            possible_causes=["poor scan matching", "map mismatch", "insufficient odometry fusion"],
        )
    ]


def _oscillation(samples, config: AnalyzerConfig) -> list[FailureFinding]:
    signs: list[tuple[float, int]] = []
    for sample in samples:
        if abs(sample.cmd_w) >= 0.05 and abs(sample.cmd_v) <= 0.08:
            signs.append((sample.t, 1 if sample.cmd_w > 0 else -1))

    for index in range(len(signs)):
        window = [item for item in signs[index:] if item[0] - signs[index][0] <= config.oscillation_window_s]
        changes = sum(1 for a, b in zip(window, window[1:]) if a[1] != b[1])
        if changes >= config.oscillation_sign_changes:
            return [
                FailureFinding(
                    failure_type="oscillation",
                    timestamp=window[0][0],
                    severity=Severity.medium,
                    confidence=0.78,
                    evidence={"sign_changes": changes, "window_s": config.oscillation_window_s},
                    possible_causes=["local planner instability", "inflation radius too large", "goal checker tolerance too strict"],
                )
            ]
    return []


def _deadlock(samples, config: AnalyzerConfig) -> list[FailureFinding]:
    start = None
    for sample in samples:
        far_from_goal = sample.goal_distance is not None and sample.goal_distance >= config.deadlock_goal_distance_m
        stalled = abs(sample.cmd_v) <= config.deadlock_speed_mps and abs(sample.cmd_w) <= 0.08 and far_from_goal
        if stalled and start is None:
            start = sample
        elif not stalled:
            start = None
        if start is not None and sample.t - start.t >= config.deadlock_duration_s:
            return [
                FailureFinding(
                    failure_type="deadlock",
                    timestamp=start.t,
                    severity=Severity.high,
                    confidence=0.74,
                    evidence={"duration_s": sample.t - start.t, "goal_distance_m": sample.goal_distance},
                    possible_causes=["blocked local costmap", "planner/controller disagreement", "recovery behavior loop"],
                )
            ]
    return []


def _narrow_passage(samples, config: AnalyzerConfig) -> list[FailureFinding]:
    active_samples = _after_first_motion(samples)
    if not active_samples:
        return []
    candidates = [
        sample for sample in active_samples
        if sample.goal_distance is not None
        and sample.goal_distance > config.goal_tolerance_m
        and sample.obstacle_distance is not None
        and sample.obstacle_distance <= config.narrow_passage_distance_m
        and abs(sample.cmd_v) < 0.12
    ]
    if not candidates:
        return []
    first = candidates[0]
    return [
        FailureFinding(
            failure_type="narrow_passage_failure",
            timestamp=first.t,
            severity=Severity.medium,
            confidence=0.68,
            evidence={"obstacle_distance_m": first.obstacle_distance, "cmd_v": first.cmd_v},
            possible_causes=["robot footprint too conservative", "inflation radius too large", "local planner sampling too sparse"],
        )
    ]


def _dynamic_obstacle_freeze(samples) -> list[FailureFinding]:
    active_samples = _after_first_motion(samples)
    if not active_samples:
        return []
    close_and_frozen = [
        sample for sample in active_samples
        if sample.goal_distance is not None
        and sample.goal_distance > 0.8
        and sample.obstacle_distance is not None
        and 0.18 < sample.obstacle_distance < 0.6
        and abs(sample.cmd_v) < 0.03
        and abs(sample.cmd_w) < 0.03
    ]
    if len(close_and_frozen) < 3:
        return []
    first = close_and_frozen[0]
    return [
        FailureFinding(
            failure_type="dynamic_obstacle_freeze",
            timestamp=first.t,
            severity=Severity.medium,
            confidence=0.61,
            evidence={"samples": len(close_and_frozen), "first_obstacle_distance_m": first.obstacle_distance},
            possible_causes=["obstacle persistence too long", "velocity obstacle over-conservative", "scene not clearing in costmap"],
        )
    ]


def _after_first_motion(samples, speed_threshold: float = 0.05):
    for index, sample in enumerate(samples):
        if abs(sample.cmd_v) > speed_threshold or abs(sample.cmd_w) > speed_threshold:
            return samples[index:]
    return []


def _planner_divergence(run: NavigationRun, config: AnalyzerConfig) -> list[FailureFinding]:
    if not run.planned_path or not run.samples:
        return []
    samples = run.samples
    planned_path_time = run.metadata.get("planned_path_time")
    if isinstance(planned_path_time, int | float):
        samples = [sample for sample in run.samples if sample.t >= float(planned_path_time)]
        if not samples:
            samples = [run.samples[-1]]

    worst_distance = 0.0
    worst_t = samples[0].t
    worst_sample = samples[0]
    for sample in samples:
        distance = min(_distance(sample.pose, point) for point in run.planned_path)
        if distance > worst_distance:
            worst_distance = distance
            worst_t = sample.t
            worst_sample = sample
    if worst_distance < config.planner_divergence_m:
        return []
    route_context = _route_context(run, worst_sample)
    evidence = {
        "max_distance_from_plan_m": worst_distance,
        "planned_path_time": planned_path_time,
        "planned_path_topic": run.metadata.get("planned_path_topic"),
        **route_context,
    }
    possible_causes = ["stale global plan", "controller tracking failure", "unexpected obstacle forcing detour"]
    if route_context["route_context_available"]:
        possible_causes = [
            "local trajectory diverged from route corridor",
            "route handler stale or mismatched with planner output",
            *possible_causes,
        ]
    return [
        FailureFinding(
            failure_type="planner_divergence",
            timestamp=worst_t,
            severity=Severity.high,
            confidence=0.78 if route_context["route_context_available"] else 0.7,
            evidence=evidence,
            possible_causes=possible_causes,
        )
    ]


def _route_context(run: NavigationRun, sample) -> dict:
    route_summary = run.metadata.get("route_summary")
    if not isinstance(route_summary, dict):
        return {"route_context_available": False}

    goal_pose = route_summary.get("goal_pose")
    route_goal_distance = None
    if isinstance(goal_pose, dict) and isinstance(goal_pose.get("x"), int | float) and isinstance(goal_pose.get("y"), int | float):
        route_goal_distance = _distance(sample.pose, Point2D(x=float(goal_pose["x"]), y=float(goal_pose["y"])))

    preferred_ids = route_summary.get("preferred_ids")
    if isinstance(preferred_ids, list):
        preferred_ids = preferred_ids[:20]
    else:
        preferred_ids = []

    return {
        "route_context_available": True,
        "route_topic": run.metadata.get("route_topic"),
        "route_time": run.metadata.get("route_time"),
        "route_segment_count": route_summary.get("segment_count"),
        "route_primitive_count": route_summary.get("primitive_count"),
        "route_preferred_ids": preferred_ids,
        "route_goal_distance_m": route_goal_distance,
    }


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)
