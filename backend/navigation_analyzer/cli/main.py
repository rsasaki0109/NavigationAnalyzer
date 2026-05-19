from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from navigation_analyzer.analysis import analyze_run, build_diagnosis_pack
from navigation_analyzer.api import create_app
from navigation_analyzer.benchmarking import compare_to_baseline, evaluate_benchmark, load_thresholds, render_benchmark_markdown
from navigation_analyzer.config import load_config
from navigation_analyzer.io import read_navigation_run
from navigation_analyzer.reporting import render_diagnosis_markdown, render_markdown_report

app = typer.Typer(help="NavigationAnalyzer: CLI-first navigation observability for ROS2/Nav2.")


@app.command()
def analyze(
    bag: Path = typer.Option(..., "--bag", "-b", help="ROS2 bag directory or canonical JSON input."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Analyzer YAML/JSON config."),
    out: Path = typer.Option(Path("outputs/analysis"), "--out", "-o", help="Output directory."),
) -> None:
    """Analyze one run and emit JSON + Markdown artifacts."""

    analyzer_config = load_config(config)
    artifact = analyze_run(read_navigation_run(bag, analyzer_config), analyzer_config)
    out.mkdir(parents=True, exist_ok=True)
    analysis_path = out / "analysis.json"
    report_path = out / "report.md"
    diagnosis_pack_path = out / "diagnosis_pack.json"
    diagnosis_md_path = out / "diagnosis.md"
    artifact.write_json(analysis_path)
    report_path.write_text(render_markdown_report(artifact), encoding="utf-8")
    diagnosis_pack = build_diagnosis_pack(artifact)
    diagnosis_pack.write_json(diagnosis_pack_path)
    diagnosis_md_path.write_text(render_diagnosis_markdown(diagnosis_pack), encoding="utf-8")
    typer.echo(f"Wrote {analysis_path}")
    typer.echo(f"Wrote {report_path}")
    typer.echo(f"Wrote {diagnosis_pack_path}")
    typer.echo(f"Wrote {diagnosis_md_path}")


@app.command()
def benchmark(
    bag: list[Path] = typer.Option(..., "--bag", "-b", help="Bag or canonical JSON input. Repeat for comparisons."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Analyzer YAML/JSON config."),
    thresholds: Path | None = typer.Option(None, "--thresholds", help="Benchmark threshold YAML/JSON config."),
    out: Path = typer.Option(Path("outputs/benchmark.json"), "--out", "-o", help="Benchmark JSON output."),
    report: Path | None = typer.Option(None, "--report", help="Optional Markdown benchmark report output."),
    fail_on_regression: bool = typer.Option(False, "--fail-on-regression", help="Exit non-zero when thresholds fail."),
) -> None:
    """Run comparable benchmark analysis over one or more runs."""

    analyzer_config = load_config(config)
    threshold_config = load_thresholds(thresholds)
    rows = []
    for bag_path in bag:
        artifact = analyze_run(read_navigation_run(bag_path, analyzer_config), analyzer_config)
        stopped_velocity_threshold = (
            threshold_config.goal.stopped_velocity_mps if threshold_config and threshold_config.goal.stopped_velocity_mps else 0.05
        )
        rows.append(
            {
                "run_id": artifact.run.run_id,
                "source": artifact.run.source,
                "metrics": {key: metric.value for key, metric in artifact.metrics.items()},
                "failures": [failure.model_dump(mode="json") for failure in artifact.failures],
                "diagnostics": [diagnostic.model_dump(mode="json") for diagnostic in artifact.diagnostics],
                "final_sample": artifact.run.samples[-1].model_dump(mode="json") if artifact.run.samples else None,
                "derived": {
                    "final_stopped_duration_s": _final_stopped_duration(artifact.run.samples, stopped_velocity_threshold),
                    "stopped_velocity_threshold_mps": stopped_velocity_threshold,
                },
            }
        )
    threshold_result = evaluate_benchmark(rows, threshold_config)
    payload = {
        "schema_version": "navigation-analyzer.benchmark.v1",
        "summary": _benchmark_summary(rows),
        "thresholds": threshold_result,
        "comparisons": compare_to_baseline(rows),
        "runs": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(f"Wrote {out}")
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_benchmark_markdown(payload), encoding="utf-8")
        typer.echo(f"Wrote {report}")
    for row in rows:
        metrics = row["metrics"]
        typer.echo(
            f"{row['run_id']}: success={metrics['success_rate']} "
            f"path={metrics['path_length']:.2f}m failures={len(row['failures'])}"
        )
    if threshold_result["enabled"]:
        status = "passed" if threshold_result["passed"] else "failed"
        typer.echo(f"thresholds: {status}")
    if fail_on_regression and not threshold_result["passed"]:
        raise typer.Exit(code=2)


@app.command()
def convert(
    bag: Path = typer.Option(..., "--bag", "-b", help="ROS2 bag directory or canonical JSON input."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Analyzer YAML/JSON config."),
    out: Path = typer.Option(Path("outputs/navigation_run.json"), "--out", "-o", help="Canonical JSON output."),
) -> None:
    """Convert a bag or JSON input into canonical NavigationRun JSON."""

    run = read_navigation_run(bag, load_config(config))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Wrote {out}")


@app.command()
def report(
    analysis: Path = typer.Option(..., "--analysis", "-a", help="analysis.json path."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Markdown report output path."),
) -> None:
    """Render a Markdown report from an existing analysis artifact."""

    from navigation_analyzer.models import AnalysisArtifact

    artifact = AnalysisArtifact.model_validate_json(analysis.read_text(encoding="utf-8"))
    markdown = render_markdown_report(artifact)
    if out is None:
        typer.echo(markdown)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        typer.echo(f"Wrote {out}")


@app.command()
def serve(
    analysis: Path = typer.Option(Path("outputs/analysis/analysis.json"), "--analysis", "-a", help="analysis.json path."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port."),
) -> None:
    """Serve analysis artifacts through the local API for the web UI."""

    uvicorn.run(create_app(analysis), host=host, port=port)


def _benchmark_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"run_count": 0}
    metric_names = sorted({name for row in rows for name in row["metrics"]})
    metric_means = {}
    for name in metric_names:
        values = [row["metrics"].get(name) for row in rows]
        numeric = [value for value in values if isinstance(value, int | float)]
        if numeric:
            metric_means[f"{name}_mean"] = sum(numeric) / len(numeric)
    failure_type_counts: dict[str, int] = {}
    diagnostic_type_counts: dict[str, int] = {}
    for row in rows:
        for failure in row["failures"]:
            failure_type = failure["failure_type"]
            failure_type_counts[failure_type] = failure_type_counts.get(failure_type, 0) + 1
        for diagnostic in row.get("diagnostics", []):
            diagnostic_type = diagnostic["diagnostic_type"]
            diagnostic_type_counts[diagnostic_type] = diagnostic_type_counts.get(diagnostic_type, 0) + 1
    return {
        "run_count": len(rows),
        "metric_means": metric_means,
        "failure_type_counts": failure_type_counts,
        "diagnostic_type_counts": diagnostic_type_counts,
    }


def _final_stopped_duration(samples, speed_threshold: float) -> float:
    if not samples:
        return 0.0
    stopped_since = samples[-1].t
    last_t = samples[-1].t
    for sample in reversed(samples):
        speed = abs(sample.cmd_v) + abs(sample.cmd_w)
        if speed > speed_threshold:
            break
        stopped_since = sample.t
    return max(0.0, last_t - stopped_since)


if __name__ == "__main__":
    app()
