from __future__ import annotations

from navigation_analyzer.models import AnalyzerConfig, DiagnosticFinding, DiagnosticLevel, MetricResult, NavigationRun


def generate_diagnostics(
    run: NavigationRun,
    metrics: dict[str, MetricResult],
    config: AnalyzerConfig,
) -> list[DiagnosticFinding]:
    if not run.samples:
        return []

    diagnostics: list[DiagnosticFinding] = []
    diagnostics.extend(_goal_reached_route_progress_mismatch(run, metrics, config))
    diagnostics.extend(_route_lanelet_deviation(run, metrics, config))
    diagnostics.extend(_nav2_goal_tolerance_violation(run, metrics, config))
    return diagnostics


def _goal_reached_route_progress_mismatch(
    run: NavigationRun,
    metrics: dict[str, MetricResult],
    config: AnalyzerConfig,
) -> list[DiagnosticFinding]:
    success = _metric_number(metrics, "success_rate")
    progress = _metric_number(metrics, "route_lanelet_progress_ratio")
    remaining = _metric_number(metrics, "route_lanelet_remaining_distance")
    matched_count = _metric_number(metrics, "route_lanelet_matched_count")
    if success != 1.0 or progress is None or remaining is None:
        return []
    if matched_count is not None and matched_count <= 0:
        return []
    if progress >= config.route_progress_mismatch_ratio or remaining < config.route_progress_mismatch_remaining_m:
        return []

    return [
        DiagnosticFinding(
            diagnostic_type="goal_reached_route_progress_mismatch",
            timestamp=run.samples[-1].t,
            level=DiagnosticLevel.warning,
            confidence=0.74,
            summary="Goal tolerance was satisfied before the matched lanelet route centerline was fully traversed.",
            evidence={
                "success_rate": success,
                "route_lanelet_progress_ratio": progress,
                "route_lanelet_remaining_distance_m": remaining,
                "route_lanelet_matched_count": matched_count,
                "goal_distance_m": _metric_number(metrics, "goal_distance"),
                "goal_source": run.metadata.get("goal_source"),
                "route_topic": run.metadata.get("route_topic"),
                "route_preferred_ids": _route_preferred_ids(run),
            },
            recommendations=[
                "Check whether the mission goal lies before the end of the final lanelet.",
                "Compare Autoware goal checker tolerance with route completion criteria.",
                "Inspect the matched lanelet sequence before treating this as a navigation failure.",
            ],
        )
    ]


def _route_lanelet_deviation(
    run: NavigationRun,
    metrics: dict[str, MetricResult],
    config: AnalyzerConfig,
) -> list[DiagnosticFinding]:
    max_distance = _metric_number(metrics, "route_lanelet_max_centerline_distance")
    matched_count = _metric_number(metrics, "route_lanelet_matched_count")
    if max_distance is None or matched_count is None or matched_count <= 0:
        return []
    if max_distance < config.route_lanelet_deviation_warning_m:
        return []

    return [
        DiagnosticFinding(
            diagnostic_type="route_lanelet_deviation",
            timestamp=run.samples[-1].t,
            level=DiagnosticLevel.warning,
            confidence=0.7,
            summary="Trajectory deviated from the matched route lanelet centerline beyond the configured warning threshold.",
            evidence={
                "route_lanelet_max_centerline_distance_m": max_distance,
                "route_lanelet_deviation_warning_m": config.route_lanelet_deviation_warning_m,
                "route_lanelet_mean_centerline_distance_m": _metric_number(metrics, "route_lanelet_mean_centerline_distance"),
                "route_lanelet_matched_count": matched_count,
                "route_preferred_ids": _route_preferred_ids(run),
            },
            recommendations=[
                "Inspect localization, controller tracking, and lanelet matching around the maximum deviation window.",
                "Tune the warning threshold for vehicle footprint and route geometry before using it as a benchmark gate.",
            ],
        )
    ]


def _nav2_goal_tolerance_violation(
    run: NavigationRun,
    metrics: dict[str, MetricResult],
    config: AnalyzerConfig,
) -> list[DiagnosticFinding]:
    if not _is_nav2_run(run):
        return []

    goal_distance = _metric_number(metrics, "goal_distance")
    yaw_error = _metric_number(metrics, "final_yaw_error")
    if goal_distance is None and yaw_error is None:
        return []

    xy_tolerance = config.nav2_xy_goal_tolerance_m
    yaw_tolerance = config.nav2_yaw_goal_tolerance_rad

    xy_pass: bool | None = None if goal_distance is None else goal_distance <= xy_tolerance
    yaw_pass: bool | None = None if yaw_error is None else abs(yaw_error) <= yaw_tolerance

    if xy_pass is not False and yaw_pass is not False:
        return []

    violations: list[str] = []
    if xy_pass is False:
        violations.append("xy")
    if yaw_pass is False:
        violations.append("yaw")

    success_rate = _metric_number(metrics, "success_rate")
    return [
        DiagnosticFinding(
            diagnostic_type="nav2_goal_tolerance_violation",
            timestamp=run.samples[-1].t,
            level=DiagnosticLevel.warning,
            confidence=0.8,
            summary=(
                "Final pose violates Nav2 SimpleGoalChecker tolerance on "
                + " and ".join(violations)
                + "."
            ),
            evidence={
                "axes_violated": violations,
                "nav2_xy_goal_tolerance_m": xy_tolerance,
                "nav2_yaw_goal_tolerance_rad": yaw_tolerance,
                "final_goal_distance_m": goal_distance,
                "final_yaw_error_rad": yaw_error,
                "xy_pass": xy_pass,
                "yaw_pass": yaw_pass,
                "success_rate_at_audit": success_rate,
                "final_lateral_error_m": _metric_number(metrics, "final_lateral_error"),
                "final_longitudinal_error_m": _metric_number(metrics, "final_longitudinal_error"),
            },
            recommendations=[
                "Compare analyzer goal_tolerance_m with Nav2 SimpleGoalChecker xy_goal_tolerance and yaw_goal_tolerance.",
                "If success_rate is 1.0 but axes_violated is non-empty, the analyzer tolerance is more lenient than Nav2's; tighten it for CI.",
                "Inspect controller angular saturation and goal yaw target when yaw violations recur.",
            ],
        )
    ]


def _is_nav2_run(run: NavigationRun) -> bool:
    stack = run.metadata.get("stack")
    if isinstance(stack, str) and stack.lower() == "nav2":
        return True
    selected_topics = run.metadata.get("selected_topics")
    if isinstance(selected_topics, dict):
        recovery = selected_topics.get("recovery")
        if isinstance(recovery, list):
            for topic in recovery:
                if isinstance(topic, str) and ("behavior_server" in topic or "recoveries" in topic):
                    return True
    return False


def _metric_number(metrics: dict[str, MetricResult], name: str) -> float | None:
    metric = metrics.get(name)
    value = metric.value if metric is not None else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _route_preferred_ids(run: NavigationRun) -> list[int]:
    route_summary = run.metadata.get("route_summary")
    if not isinstance(route_summary, dict):
        return []
    values = route_summary.get("preferred_ids")
    if not isinstance(values, list):
        return []
    return [value for value in values[:20] if isinstance(value, int)]
