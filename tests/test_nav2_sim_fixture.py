from pathlib import Path

import pytest

from navigation_analyzer.analysis import analyze_run
from navigation_analyzer.config import load_config
from navigation_analyzer.io import read_navigation_run


def test_nav2_sim_fixture_preserves_success_and_failure_warning():
    run = read_navigation_run(Path("examples/nav2_sim_success_003/navigation_run.json"))
    artifact = analyze_run(run, load_config(Path("config/default.yaml")))

    assert artifact.metrics["success_rate"].value == 1.0
    assert artifact.metrics["time_to_goal"].value == pytest.approx(3.744, abs=0.01)
    assert artifact.metrics["goal_distance"].value == pytest.approx(0.181, abs=0.01)
    assert artifact.metrics["path_length"].value == pytest.approx(0.721, abs=0.03)
    assert artifact.metrics["final_lateral_error"].value == pytest.approx(-0.058, abs=0.01)
    assert artifact.metrics["final_longitudinal_error"].value == pytest.approx(-0.171, abs=0.01)
    assert artifact.metrics["final_yaw_error"].value == pytest.approx(0.191, abs=0.01)
    assert artifact.metrics["final_stopped_duration"].value == pytest.approx(17.388, abs=0.01)
    assert [failure.failure_type for failure in artifact.failures] == ["narrow_passage_failure"]
