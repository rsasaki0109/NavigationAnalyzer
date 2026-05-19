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


def test_nav2_goal_tolerance_xy_violation_emits_warning():
    run = NavigationRun(
        run_id="nav2-xy-violation",
        source="test",
        samples=[NavigationSample(t=10.0, pose=Pose2D(x=1.0, y=0.0, yaw=0.1))],
        metadata={"stack": "nav2"},
    )
    metrics = {
        "success_rate": metric("success_rate", 1.0),
        "goal_distance": metric("goal_distance", 0.40),
        "final_yaw_error": metric("final_yaw_error", 0.1),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig())

    nav2_diagnostics = [d for d in diagnostics if d.diagnostic_type == "nav2_goal_tolerance_violation"]
    assert len(nav2_diagnostics) == 1
    finding = nav2_diagnostics[0]
    assert finding.level == "warning"
    assert finding.evidence["axes_violated"] == ["xy"]
    assert finding.evidence["xy_pass"] is False
    assert finding.evidence["yaw_pass"] is True
    assert finding.evidence["nav2_xy_goal_tolerance_m"] == 0.25
    assert finding.evidence["success_rate_at_audit"] == 1.0


def test_nav2_goal_tolerance_yaw_violation_detected_via_recovery_topic():
    run = NavigationRun(
        run_id="nav2-yaw-violation",
        source="test",
        samples=[NavigationSample(t=12.0, pose=Pose2D(x=0.0, y=0.0, yaw=0.5))],
        metadata={
            "selected_topics": {"recovery": ["/behavior_server/transition_event"]},
        },
    )
    metrics = {
        "success_rate": metric("success_rate", 1.0),
        "goal_distance": metric("goal_distance", 0.10),
        "final_yaw_error": metric("final_yaw_error", 0.50),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig())

    nav2_diagnostics = [d for d in diagnostics if d.diagnostic_type == "nav2_goal_tolerance_violation"]
    assert len(nav2_diagnostics) == 1
    assert nav2_diagnostics[0].evidence["axes_violated"] == ["yaw"]


def test_nav2_goal_tolerance_within_limits_emits_nothing():
    run = NavigationRun(
        run_id="nav2-within",
        source="test",
        samples=[NavigationSample(t=5.0, pose=Pose2D(x=0.0, y=0.0, yaw=0.1))],
        metadata={"stack": "nav2"},
    )
    metrics = {
        "success_rate": metric("success_rate", 1.0),
        "goal_distance": metric("goal_distance", 0.18),
        "final_yaw_error": metric("final_yaw_error", 0.1),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig())

    assert all(d.diagnostic_type != "nav2_goal_tolerance_violation" for d in diagnostics)


def test_nav2_goal_tolerance_skips_non_nav2_run():
    run = NavigationRun(
        run_id="non-nav2",
        source="test",
        samples=[NavigationSample(t=5.0, pose=Pose2D(x=0.0, y=0.0, yaw=0.1))],
        metadata={"stack": "autoware"},
    )
    metrics = {
        "success_rate": metric("success_rate", 0.0),
        "goal_distance": metric("goal_distance", 5.0),
        "final_yaw_error": metric("final_yaw_error", 0.8),
    }

    diagnostics = generate_diagnostics(run, metrics, AnalyzerConfig())

    assert all(d.diagnostic_type != "nav2_goal_tolerance_violation" for d in diagnostics)
