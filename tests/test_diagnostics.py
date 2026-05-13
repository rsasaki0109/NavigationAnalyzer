from navigation_analyzer.analysis.diagnostics import generate_diagnostics
from navigation_analyzer.models import AnalyzerConfig, MetricResult, NavigationRun, NavigationSample, Pose2D


def metric(name: str, value: float | int | None) -> MetricResult:
    return MetricResult(name=name, value=value, unit="", description=name)


def test_goal_reached_route_progress_mismatch_diagnostic():
    run = NavigationRun(
        run_id="route-mismatch",
        source="test",
        samples=[NavigationSample(t=12.0, pose=Pose2D(x=10.0, y=0.0, yaw=0.0))],
        metadata={
            "goal_source": "goal_topic",
            "route_topic": "/planning/mission_planning/route",
            "route_summary": {"preferred_ids": [9803, 127]},
        },
    )
    metrics = {
        "success_rate": metric("success_rate", 1.0),
        "goal_distance": metric("goal_distance", 0.03),
        "route_lanelet_progress_ratio": metric("route_lanelet_progress_ratio", 0.79),
        "route_lanelet_remaining_distance": metric("route_lanelet_remaining_distance", 14.0),
        "route_lanelet_matched_count": metric("route_lanelet_matched_count", 2),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig())

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.diagnostic_type == "goal_reached_route_progress_mismatch"
    assert diagnostic.level == "warning"
    assert diagnostic.evidence["route_lanelet_progress_ratio"] == 0.79
    assert diagnostic.evidence["route_preferred_ids"] == [9803, 127]


def test_route_lanelet_deviation_diagnostic():
    run = NavigationRun(
        run_id="route-deviation",
        source="test",
        samples=[NavigationSample(t=8.0, pose=Pose2D(x=10.0, y=2.0, yaw=0.0))],
        metadata={"route_summary": {"preferred_ids": [100]}},
    )
    metrics = {
        "route_lanelet_max_centerline_distance": metric("route_lanelet_max_centerline_distance", 1.6),
        "route_lanelet_mean_centerline_distance": metric("route_lanelet_mean_centerline_distance", 0.9),
        "route_lanelet_matched_count": metric("route_lanelet_matched_count", 1),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig(route_lanelet_deviation_warning_m=1.0))

    assert len(diagnostics) == 1
    assert diagnostics[0].diagnostic_type == "route_lanelet_deviation"
    assert diagnostics[0].evidence["route_lanelet_deviation_warning_m"] == 1.0
