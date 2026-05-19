from navigation_analyzer.analysis import analyze_run
from navigation_analyzer.analysis.failures import detect_failures
from navigation_analyzer.analysis.metrics import compute_metrics
from navigation_analyzer.models import (
    AnalyzerConfig,
    NavigationRun,
    NavigationSample,
    Point2D,
    Pose2D,
)


def _make_run(ages: list[float | None]) -> NavigationRun:
    samples = []
    for i, age in enumerate(ages):
        samples.append(
            NavigationSample(
                t=float(i) * 0.5,
                pose=Pose2D(x=float(i) * 0.25, y=0.0, yaw=0.0),
                cmd_v=0.5,
                cmd_w=0.0,
                goal_distance=max(0.0, 5.0 - float(i) * 0.25),
                tf_age_s=age,
            )
        )
    return NavigationRun(
        run_id="tf-test",
        source="test.json",
        goal=Point2D(x=5.0, y=0.0),
        planned_path=[Point2D(x=float(i) * 0.25, y=0.0) for i in range(len(samples))],
        samples=samples,
        metadata={"stack": "nav2"},
    )


def test_tf_health_metrics_return_none_when_no_data():
    run = _make_run([None] * 5)
    metrics = compute_metrics(run, AnalyzerConfig())
    assert metrics["tf_max_age_s"].value is None
    assert metrics["tf_mean_age_s"].value is None
    assert metrics["tf_health_sample_coverage"].value == 0.0


def test_tf_health_metrics_compute_from_partial_coverage():
    run = _make_run([0.05, None, 0.1, 0.2, 0.05])
    metrics = compute_metrics(run, AnalyzerConfig())
    assert metrics["tf_max_age_s"].value == 0.2
    assert metrics["tf_mean_age_s"].value == 0.1
    assert metrics["tf_health_sample_coverage"].value == 0.8


def test_tf_dropout_fires_when_sustained_above_threshold():
    # samples at 0.5s spacing; 0.9s for 5 samples = 2.0s sustained, above default 1.0s.
    ages = [0.05, 0.05, 0.9, 0.9, 0.9, 0.9, 0.9, 0.05, 0.05, 0.05]
    failures = detect_failures(_make_run(ages), AnalyzerConfig())
    tf = [f for f in failures if f.failure_type == "tf_dropout"]
    assert len(tf) == 1
    finding = tf[0]
    assert finding.evidence["peak_tf_age_s"] == 0.9
    assert finding.evidence["window_duration_s"] == 2.0
    assert finding.severity == "medium"  # 0.9 < 2 * 0.5 threshold


def test_tf_dropout_severity_high_when_age_doubled():
    ages = [0.05, 1.5, 1.5, 1.5, 1.5, 0.05]
    failures = detect_failures(_make_run(ages), AnalyzerConfig())
    tf = [f for f in failures if f.failure_type == "tf_dropout"]
    assert len(tf) == 1
    assert tf[0].severity == "high"


def test_tf_dropout_does_not_fire_for_brief_blip():
    ages = [0.05, 0.05, 0.9, 0.05, 0.05]  # only 0.5s above threshold; below 1.0s sustained
    failures = detect_failures(_make_run(ages), AnalyzerConfig())
    assert all(f.failure_type != "tf_dropout" for f in failures)


def test_tf_dropout_is_silent_when_no_tf_data():
    failures = detect_failures(_make_run([None, None, None, None]), AnalyzerConfig())
    assert all(f.failure_type != "tf_dropout" for f in failures)


def test_analyze_run_emits_tf_dropout_failure():
    ages = [0.05, 0.9, 0.9, 0.9, 0.9, 0.9, 0.05]
    artifact = analyze_run(_make_run(ages), AnalyzerConfig())
    assert any(f.failure_type == "tf_dropout" for f in artifact.failures)
