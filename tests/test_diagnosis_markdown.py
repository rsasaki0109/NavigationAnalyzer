from navigation_analyzer.analysis import analyze_run, build_diagnosis_pack
from navigation_analyzer.models import (
    AnalyzerConfig,
    NavigationRun,
    NavigationSample,
    Point2D,
    Pose2D,
)
from navigation_analyzer.reporting import render_diagnosis_markdown


def _failing_run() -> NavigationRun:
    samples = []
    for i in range(20):
        samples.append(
            NavigationSample(
                t=float(i),
                pose=Pose2D(x=1.5, y=0.1, yaw=0.2 if i % 2 == 0 else -0.2),
                cmd_v=0.0,
                cmd_w=0.4 if i % 2 == 0 else -0.4,
                goal_distance=3.5,
                obstacle_distance=0.25,
                recovery_event=(i in {7, 10}),
                localization_error=0.05 + 0.05 * i,
            )
        )
    return NavigationRun(
        run_id="diag-md-failure",
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
        run_id="diag-md-success",
        source="success.json",
        goal=Point2D(x=5.0, y=0.0),
        planned_path=[Point2D(x=float(i) * 0.5, y=0.0) for i in range(11)],
        samples=samples,
        metadata={"stack": "nav2"},
    )


def test_failing_run_markdown_has_fail_header_and_hypothesis():
    pack = build_diagnosis_pack(analyze_run(_failing_run(), AnalyzerConfig()))
    markdown = render_diagnosis_markdown(pack)

    assert "# Navigation Diagnosis: diag-md-failure" in markdown
    assert "**FAIL**" in markdown
    assert "Primary failure:" in markdown
    assert "## Top Hypotheses" in markdown
    assert "hyp_001" in markdown
    assert "Evidence window `win_001`" in markdown
    assert "Profile: `nav2`" in markdown
    assert "Full artifacts:" in markdown


def test_success_run_markdown_has_pass_header_and_no_hypotheses():
    pack = build_diagnosis_pack(analyze_run(_success_run(), AnalyzerConfig()))
    markdown = render_diagnosis_markdown(pack)

    assert "**PASS**" in markdown
    assert "Primary failure:" not in markdown
    assert "No top hypotheses" in markdown
    assert "hyp_" not in markdown
    assert "## Missing Signals" in markdown
    assert "## Diagnostics" not in markdown


def test_markdown_renders_nav2_goal_tolerance_diagnostic():
    pack = build_diagnosis_pack(analyze_run(_failing_run(), AnalyzerConfig()))
    markdown = render_diagnosis_markdown(pack)

    assert "## Diagnostics" in markdown
    assert "nav2_goal_tolerance_violation" in markdown
    assert "axes_violated" in markdown
    assert "Recommendations:" in markdown
