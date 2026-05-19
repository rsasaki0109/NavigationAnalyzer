from navigation_analyzer.analysis import analyze_run, build_diagnosis_pack
from navigation_analyzer.models import (
    AnalyzerConfig,
    NavigationRun,
    NavigationSample,
    Point2D,
    Pose2D,
)


def _failing_run() -> NavigationRun:
    samples = []
    for i in range(20):
        t = float(i)
        samples.append(
            NavigationSample(
                t=t,
                pose=Pose2D(x=1.5, y=0.1, yaw=0.2 if i % 2 == 0 else -0.2),
                cmd_v=0.0,
                cmd_w=0.4 if i % 2 == 0 else -0.4,
                goal_distance=3.5,
                obstacle_distance=0.25,
                collision=False,
                recovery_event=(i in {7, 10, 15}),
                localization_error=0.05 + 0.05 * i,
            )
        )
    return NavigationRun(
        run_id="diag-pack-failure",
        source="test.json",
        goal=Point2D(x=5.0, y=0.0),
        planned_path=[Point2D(x=0.0, y=0.0), Point2D(x=5.0, y=0.0)],
        samples=samples,
        metadata={"stack": "nav2"},
    )


def _success_run() -> NavigationRun:
    samples = [
        NavigationSample(
            t=float(i),
            pose=Pose2D(x=float(i) * 0.5, y=0.0, yaw=0.0),
            cmd_v=0.5,
            cmd_w=0.0,
            goal_distance=max(0.0, 5.0 - float(i) * 0.5),
            obstacle_distance=1.2,
        )
        for i in range(11)
    ]
    return NavigationRun(
        run_id="diag-pack-success",
        source="success.json",
        goal=Point2D(x=5.0, y=0.0),
        planned_path=[Point2D(x=float(i) * 0.5, y=0.0) for i in range(11)],
        samples=samples,
        metadata={"stack": "nav2"},
    )


def test_diagnosis_pack_failing_run_emits_hypothesis_and_window():
    artifact = analyze_run(_failing_run(), AnalyzerConfig())
    pack = build_diagnosis_pack(artifact)

    assert pack.schema_version == "navigation-analyzer.diagnosis_pack.v1"
    assert pack.run.run_id == "diag-pack-failure"
    assert pack.run.profile == "nav2"
    assert pack.run.source_type == "canonical_json"
    assert pack.run.duration_s == 19.0
    assert pack.outcome.passed is False
    assert pack.outcome.failure_count >= 1
    assert pack.outcome.primary_failure is not None

    assert len(pack.top_hypotheses) == len(artifact.failures)
    assert len(pack.evidence_windows) == len(artifact.failures)
    assert len(pack.diagnostics) == len(artifact.diagnostics)

    hypothesis = pack.top_hypotheses[0]
    assert hypothesis.id.startswith("hyp_")
    assert hypothesis.evidence_window_ids
    window_id = hypothesis.evidence_window_ids[0]
    window = next(w for w in pack.evidence_windows if w.id == window_id)
    assert window.t_start <= window.t_end
    assert window.signals["sample_count"] >= 1
    assert "cmd_w" in window.signals


def test_diagnosis_pack_success_run_is_passed_and_clean():
    artifact = analyze_run(_success_run(), AnalyzerConfig())
    pack = build_diagnosis_pack(artifact)

    assert pack.outcome.passed is True
    assert pack.outcome.failure_count == 0
    assert pack.outcome.primary_failure is None
    assert pack.top_hypotheses == []
    assert pack.evidence_windows == []
    assert "localization_error" in pack.missing_signals
