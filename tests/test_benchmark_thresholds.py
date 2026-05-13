from pathlib import Path

from navigation_analyzer.benchmarking import compare_to_baseline, evaluate_benchmark, load_thresholds, render_benchmark_markdown


def test_nav2_thresholds_pass_success_fixture_row():
    thresholds = load_thresholds(Path("config/benchmark_nav2.yaml"))
    row = {
        "run_id": "ok",
        "metrics": {
            "success_rate": 1.0,
            "goal_distance": 0.18,
            "final_yaw_error": 0.1,
            "collision_count": 0,
        },
        "failures": [{"failure_type": "narrow_passage_failure", "severity": "medium"}],
        "final_sample": {"cmd_v": 0.0, "cmd_w": 0.0},
    }

    result = evaluate_benchmark([row], thresholds)

    assert result["passed"] is True
    assert result["violations"] == []


def test_nav2_thresholds_fail_deadlock_and_goal_distance():
    thresholds = load_thresholds(Path("config/benchmark_nav2.yaml"))
    row = {
        "run_id": "bad",
        "metrics": {
            "success_rate": 0.0,
            "goal_distance": 1.2,
            "final_yaw_error": 0.4,
            "collision_count": 0,
        },
        "failures": [{"failure_type": "deadlock", "severity": "high"}],
        "final_sample": {"cmd_v": 0.0, "cmd_w": 0.0},
    }

    result = evaluate_benchmark([row], thresholds)

    assert result["passed"] is False
    checks = {violation["check"] for violation in result["violations"]}
    assert "goal.require_success" in checks
    assert "goal.xy_goal_tolerance_m" in checks
    assert "goal.yaw_goal_tolerance_rad" in checks
    assert "failures.disallow_types" in checks


def test_autoware_thresholds_check_stopped_duration():
    thresholds = load_thresholds(Path("config/benchmark_autoware.yaml"))
    row = {
        "run_id": "not_stopped_long_enough",
        "metrics": {
            "success_rate": 1.0,
            "goal_distance": 0.2,
            "final_lateral_error": 0.1,
            "final_longitudinal_error": 0.1,
            "final_yaw_error": 0.1,
            "final_stopped_duration": 0.5,
            "collision_count": 0,
        },
        "failures": [],
        "final_sample": {"cmd_v": 0.0, "cmd_w": 0.0},
        "derived": {"final_stopped_duration_s": 0.5},
    }

    result = evaluate_benchmark([row], thresholds)

    assert result["passed"] is False
    assert "goal.stopped_duration_s" in {violation["check"] for violation in result["violations"]}


def test_benchmark_markdown_includes_violations():
    payload = {
        "summary": {"run_count": 1, "failure_type_counts": {"deadlock": 1}},
        "comparisons": {"baseline_run_id": "bad", "metric_deltas": []},
        "thresholds": {
            "enabled": True,
            "passed": False,
            "violations": [{"run_id": "bad", "check": "goal.require_success", "message": "success_rate must be 1.0"}],
        },
        "runs": [
            {
                "run_id": "bad",
                "metrics": {
                    "success_rate": 0.0,
                    "goal_distance": 1.2,
                    "time_to_goal": None,
                    "collision_count": 0,
                    "path_length": 3.0,
                },
                "failures": [{"failure_type": "deadlock"}],
            }
        ],
    }

    markdown = render_benchmark_markdown(payload)

    assert "Threshold Violations" in markdown
    assert "Comparisons" in markdown
    assert "goal.require_success" in markdown


def test_compare_to_baseline_flags_metric_regressions():
    rows = [
        {
            "run_id": "baseline",
            "metrics": {"success_rate": 1.0, "goal_distance": 0.2, "path_length": 1.0},
            "failures": [],
        },
        {
            "run_id": "candidate",
            "metrics": {"success_rate": 1.0, "goal_distance": 0.4, "path_length": 0.9},
            "failures": [{"failure_type": "oscillation"}],
        },
    ]

    comparisons = compare_to_baseline(rows)

    assert comparisons["baseline_run_id"] == "baseline"
    goal_delta = next(
        delta
        for delta in comparisons["metric_deltas"]
        if delta["run_id"] == "candidate" and delta["metric"] == "goal_distance"
    )
    path_delta = next(
        delta
        for delta in comparisons["metric_deltas"]
        if delta["run_id"] == "candidate" and delta["metric"] == "path_length"
    )
    failure_delta = next(
        delta
        for delta in comparisons["metric_deltas"]
        if delta["run_id"] == "candidate" and delta["metric"] == "failure_count"
    )
    assert goal_delta["regression"] is True
    assert path_delta["improvement"] is True
    assert failure_delta["regression"] is True


def test_minimum_obstacle_distance_is_higher_is_better():
    rows = [
        {"run_id": "baseline", "metrics": {"minimum_obstacle_distance": 0.3}, "failures": []},
        {"run_id": "candidate", "metrics": {"minimum_obstacle_distance": 0.1}, "failures": []},
    ]

    comparisons = compare_to_baseline(rows)

    clearance_delta = next(
        delta
        for delta in comparisons["metric_deltas"]
        if delta["run_id"] == "candidate" and delta["metric"] == "minimum_obstacle_distance"
    )
    assert clearance_delta["direction"] == "higher_is_better"
    assert clearance_delta["regression"] is True
