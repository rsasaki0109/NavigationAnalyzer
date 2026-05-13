from pathlib import Path

import pytest

from navigation_analyzer.analysis import analyze_run
from navigation_analyzer.analysis.failures import detect_failures
from navigation_analyzer.config import load_config
from navigation_analyzer.io import read_navigation_run
from navigation_analyzer.models import AnalyzerConfig, NavigationRun, NavigationSample, Point2D, Pose2D


def test_sample_analysis_detects_failures():
    run = read_navigation_run(Path("examples/sample_bag/sample_navigation.json"))
    artifact = analyze_run(run, load_config(Path("config/default.yaml")))
    assert artifact.metrics["path_length"].value > 0
    assert artifact.metrics["success_rate"].value == 0.0
    assert {failure.failure_type for failure in artifact.failures}


def test_planner_divergence_includes_autoware_route_context():
    run = NavigationRun(
        run_id="route-divergence",
        source="test",
        planned_path=[Point2D(x=0.0, y=0.0), Point2D(x=1.0, y=0.0)],
        samples=[
            NavigationSample(t=5.0, pose=Pose2D(x=3.0, y=4.0, yaw=0.0)),
            NavigationSample(t=6.0, pose=Pose2D(x=4.0, y=4.0, yaw=0.0)),
        ],
        metadata={
            "planned_path_time": 1.0,
            "planned_path_topic": "/planning/scenario_planning/trajectory",
            "route_topic": "/planning/mission_planning/route",
            "route_time": 0.5,
            "route_summary": {
                "segment_count": 2,
                "primitive_count": 2,
                "preferred_ids": [9803, 127],
                "goal_pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
            },
        },
    )

    findings = detect_failures(run, AnalyzerConfig(planner_divergence_m=1.0))
    planner = next(finding for finding in findings if finding.failure_type == "planner_divergence")

    assert planner.confidence == 0.78
    assert planner.evidence["route_context_available"] is True
    assert planner.evidence["route_topic"] == "/planning/mission_planning/route"
    assert planner.evidence["route_segment_count"] == 2
    assert planner.evidence["route_preferred_ids"] == [9803, 127]
    assert planner.evidence["route_goal_distance_m"] > 0.0
    assert "local trajectory diverged from route corridor" in planner.possible_causes


def test_route_straight_line_progress_metrics():
    run = NavigationRun(
        run_id="route-progress",
        source="test",
        goal_pose=Pose2D(x=10.0, y=0.0, yaw=0.0),
        samples=[NavigationSample(t=0.0, pose=Pose2D(x=5.0, y=1.0, yaw=0.0))],
        metadata={
            "route_summary": {
                "start_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
                "goal_pose": {"x": 10.0, "y": 0.0, "yaw": 0.0},
            }
        },
    )

    artifact = analyze_run(run, AnalyzerConfig())

    assert artifact.metrics["route_progress_ratio"].value == pytest.approx(0.5)
    assert artifact.metrics["route_straight_line_lateral_error"].value == pytest.approx(1.0)
    assert artifact.metrics["route_straight_line_remaining_distance"].value == pytest.approx(5.0)
