from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


Profile = Literal["generic", "nav2", "autoware"]


class MetricThreshold(BaseModel):
    min: float | None = None
    max: float | None = None
    equals: float | int | bool | None = None


class FailureThreshold(BaseModel):
    max_count: int | None = None
    disallow_types: list[str] = Field(default_factory=list)
    max_severity: Literal["low", "medium", "high"] | None = None


class GoalThreshold(BaseModel):
    xy_goal_tolerance_m: float | None = None
    yaw_goal_tolerance_rad: float | None = None
    stopped_velocity_mps: float | None = None
    stopped_duration_s: float | None = None
    require_success: bool = True


class BenchmarkThresholds(BaseModel):
    schema_version: str = "navigation-analyzer.thresholds.v1"
    profile: Profile = "generic"
    description: str = ""
    goal: GoalThreshold = Field(default_factory=GoalThreshold)
    metrics: dict[str, MetricThreshold] = Field(default_factory=dict)
    failures: FailureThreshold = Field(default_factory=FailureThreshold)


def load_thresholds(path: Path | None) -> BenchmarkThresholds | None:
    if path is None:
        return None
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    return BenchmarkThresholds.model_validate(data or {})


def evaluate_benchmark(rows: list[dict[str, Any]], thresholds: BenchmarkThresholds | None) -> dict[str, Any]:
    if thresholds is None:
        return {"enabled": False, "passed": True, "profile": "none", "violations": []}

    violations = []
    for row in rows:
        violations.extend(_evaluate_row(row, thresholds))

    return {
        "enabled": True,
        "passed": not violations,
        "profile": thresholds.profile,
        "description": thresholds.description,
        "violations": violations,
    }


def compare_to_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"baseline_run_id": None, "metric_deltas": []}
    baseline = rows[0]
    baseline_metrics = _comparable_metrics(baseline)
    deltas = []
    for row in rows:
        metrics = _comparable_metrics(row)
        for metric_name, value in sorted(metrics.items()):
            baseline_value = baseline_metrics.get(metric_name)
            if baseline_value is None:
                continue
            delta = value - baseline_value
            direction = _metric_direction(metric_name)
            deltas.append(
                {
                    "run_id": row["run_id"],
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "value": value,
                    "delta": delta,
                    "delta_percent": _percent_delta(baseline_value, delta),
                    "direction": direction,
                    "regression": _is_regression(baseline_value, value, direction),
                    "improvement": _is_improvement(baseline_value, value, direction),
                }
            )
    return {"baseline_run_id": baseline["run_id"], "metric_deltas": deltas}


def render_benchmark_markdown(payload: dict[str, Any]) -> str:
    rows = payload.get("runs", [])
    summary = payload.get("summary", {})
    threshold_result = payload.get("thresholds", {"enabled": False, "passed": True})
    rankings = _rankings(rows)
    lines = [
        "# Navigation Benchmark Report",
        "",
        "## Summary",
        "",
        f"- Runs: {summary.get('run_count', len(rows))}",
        f"- Thresholds: {_threshold_label(threshold_result)}",
        "",
        "## Runs",
        "",
        "| Run | Success | Goal Distance | Yaw Error | Lateral | Longitudinal | Stopped | Collisions | Failures | Diagnostics | Path Length |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        metrics = row["metrics"]
        lines.append(
            "| {run_id} | {success} | {goal_distance} | {yaw_error} | {lateral} | {longitudinal} | {stopped} | {collisions} | {failures} | {diagnostics} | {path_length} |".format(
                run_id=row["run_id"],
                success=_fmt(metrics.get("success_rate")),
                goal_distance=_fmt(metrics.get("goal_distance")),
                yaw_error=_fmt(metrics.get("final_yaw_error")),
                lateral=_fmt(metrics.get("final_lateral_error")),
                longitudinal=_fmt(metrics.get("final_longitudinal_error")),
                stopped=_fmt(metrics.get("final_stopped_duration")),
                collisions=_fmt(metrics.get("collision_count")),
                failures=len(row.get("failures", [])),
                diagnostics=len(row.get("diagnostics", [])),
                path_length=_fmt(metrics.get("path_length")),
            )
        )

    lines.extend(["", "## Comparisons", ""])
    if not rows:
        lines.append("No runs to compare.")
    else:
        lines.extend(
            [
                f"- Best goal distance: `{rankings['best_goal_distance']['run_id']}` ({_fmt(rankings['best_goal_distance']['value'])} m)",
                f"- Shortest path: `{rankings['shortest_path']['run_id']}` ({_fmt(rankings['shortest_path']['value'])} m)",
                f"- Fastest goal reach: `{rankings['fastest_goal']['run_id']}` ({_fmt(rankings['fastest_goal']['value'])} s)",
                f"- Fewest failures: `{rankings['fewest_failures']['run_id']}` ({rankings['fewest_failures']['value']})",
            ]
        )

    lines.extend(["", "## Failure Types", ""])
    failure_type_counts = summary.get("failure_type_counts", {})
    if failure_type_counts:
        for failure_type, count in sorted(failure_type_counts.items()):
            lines.append(f"- `{failure_type}`: {count}")
    else:
        lines.append("No failures detected.")

    lines.extend(["", "## Diagnostic Types", ""])
    diagnostic_type_counts = summary.get("diagnostic_type_counts", {})
    if diagnostic_type_counts:
        for diagnostic_type, count in sorted(diagnostic_type_counts.items()):
            lines.append(f"- `{diagnostic_type}`: {count}")
    else:
        lines.append("No diagnostics emitted.")

    lines.extend(["", "## Threshold Violations", ""])
    violations = threshold_result.get("violations", [])
    if not violations:
        lines.append("No threshold violations.")
    else:
        for violation in violations:
            lines.append(
                "- `{run_id}` `{check}`: {message}".format(
                    run_id=violation["run_id"],
                    check=violation["check"],
                    message=violation["message"],
                )
            )

    lines.extend(["", "## Baseline Diffs", ""])
    comparisons = payload.get("comparisons", {})
    baseline_run_id = comparisons.get("baseline_run_id")
    deltas = comparisons.get("metric_deltas", [])
    regressions = [delta for delta in deltas if delta.get("regression")]
    if not baseline_run_id:
        lines.append("No baseline run.")
    elif not regressions:
        lines.append(f"No regressions against baseline `{baseline_run_id}`.")
    else:
        lines.extend(
            [
                f"Baseline: `{baseline_run_id}`",
                "",
                "| Run | Metric | Baseline | Value | Delta | Delta % |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for delta in regressions:
            lines.append(
                "| {run_id} | `{metric}` | {baseline} | {value} | {diff} | {percent} |".format(
                    run_id=delta["run_id"],
                    metric=delta["metric"],
                    baseline=_fmt(delta["baseline"]),
                    value=_fmt(delta["value"]),
                    diff=_fmt(delta["delta"]),
                    percent=_fmt(delta["delta_percent"]),
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def _evaluate_row(row: dict[str, Any], thresholds: BenchmarkThresholds) -> list[dict[str, Any]]:
    violations = []
    metrics = row.get("metrics", {})
    failures = row.get("failures", [])

    if thresholds.goal.require_success and metrics.get("success_rate") != 1.0:
        violations.append(_violation(row, "goal.require_success", "success_rate must be 1.0"))

    xy_tolerance = thresholds.goal.xy_goal_tolerance_m
    if xy_tolerance is not None:
        goal_distance = metrics.get("goal_distance")
        if goal_distance is None or goal_distance > xy_tolerance:
            violations.append(
                _violation(row, "goal.xy_goal_tolerance_m", f"goal_distance {goal_distance} exceeds {xy_tolerance}")
            )

    yaw_tolerance = thresholds.goal.yaw_goal_tolerance_rad
    if yaw_tolerance is not None:
        yaw_error = metrics.get("final_yaw_error")
        if yaw_error is None or abs(yaw_error) > yaw_tolerance:
            violations.append(
                _violation(row, "goal.yaw_goal_tolerance_rad", f"final_yaw_error {yaw_error} exceeds {yaw_tolerance}")
            )

    stopped_velocity = thresholds.goal.stopped_velocity_mps
    if stopped_velocity is not None:
        final_speed = _final_speed(row)
        if final_speed is None or final_speed > stopped_velocity:
            violations.append(
                _violation(row, "goal.stopped_velocity_mps", f"final commanded speed {final_speed} exceeds {stopped_velocity}")
            )

    stopped_duration = thresholds.goal.stopped_duration_s
    if stopped_duration is not None:
        observed_duration = metrics.get("final_stopped_duration")
        if observed_duration is None:
            observed_duration = row.get("derived", {}).get("final_stopped_duration_s")
        if observed_duration is None or observed_duration < stopped_duration:
            violations.append(
                _violation(
                    row,
                    "goal.stopped_duration_s",
                    f"final stopped duration {observed_duration} is below {stopped_duration}",
                )
            )

    for metric_name, threshold in thresholds.metrics.items():
        value = metrics.get(metric_name)
        violations.extend(_evaluate_metric(row, metric_name, value, threshold))

    if thresholds.failures.max_count is not None and len(failures) > thresholds.failures.max_count:
        violations.append(
            _violation(row, "failures.max_count", f"failure count {len(failures)} exceeds {thresholds.failures.max_count}")
        )

    disallowed = set(thresholds.failures.disallow_types)
    for failure in failures:
        if failure["failure_type"] in disallowed:
            violations.append(_violation(row, "failures.disallow_types", f"disallowed failure {failure['failure_type']}"))

    max_severity = thresholds.failures.max_severity
    if max_severity is not None:
        max_allowed = _severity_rank(max_severity)
        for failure in failures:
            if _severity_rank(failure["severity"]) > max_allowed:
                violations.append(
                    _violation(row, "failures.max_severity", f"{failure['failure_type']} severity {failure['severity']} exceeds {max_severity}")
                )

    return violations


def _evaluate_metric(
    row: dict[str, Any],
    metric_name: str,
    value: Any,
    threshold: MetricThreshold,
) -> list[dict[str, Any]]:
    violations = []
    if threshold.equals is not None and value != threshold.equals:
        violations.append(_violation(row, f"metrics.{metric_name}.equals", f"{metric_name} {value} != {threshold.equals}"))
    if threshold.min is not None and (value is None or value < threshold.min):
        violations.append(_violation(row, f"metrics.{metric_name}.min", f"{metric_name} {value} < {threshold.min}"))
    if threshold.max is not None and (value is None or value > threshold.max):
        violations.append(_violation(row, f"metrics.{metric_name}.max", f"{metric_name} {value} > {threshold.max}"))
    return violations


def _final_speed(row: dict[str, Any]) -> float | None:
    sample = row.get("final_sample")
    if sample is None:
        return None
    cmd_v = float(sample.get("cmd_v", 0.0))
    cmd_w = float(sample.get("cmd_w", 0.0))
    return abs(cmd_v) + abs(cmd_w)


def _violation(row: dict[str, Any], check: str, message: str) -> dict[str, Any]:
    return {"run_id": row["run_id"], "check": check, "message": message}


def _severity_rank(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}[severity]


def _threshold_label(threshold_result: dict[str, Any]) -> str:
    if not threshold_result.get("enabled"):
        return "disabled"
    return "passed" if threshold_result.get("passed") else "failed"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _rankings(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "best_goal_distance": _best_metric(rows, "goal_distance"),
        "shortest_path": _best_metric(rows, "path_length"),
        "fastest_goal": _best_metric(rows, "time_to_goal"),
        "fewest_failures": min(
            ({"run_id": row["run_id"], "value": len(row.get("failures", []))} for row in rows),
            key=lambda item: item["value"],
            default={"run_id": "n/a", "value": None},
        ),
    }


def _best_metric(rows: list[dict[str, Any]], metric_name: str) -> dict[str, Any]:
    candidates = [
        {"run_id": row["run_id"], "value": row.get("metrics", {}).get(metric_name)}
        for row in rows
        if row.get("metrics", {}).get(metric_name) is not None
    ]
    return min(candidates, key=lambda item: item["value"], default={"run_id": "n/a", "value": None})


def _comparable_metrics(row: dict[str, Any]) -> dict[str, float]:
    metrics = {
        name: float(value)
        for name, value in row.get("metrics", {}).items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    metrics["failure_count"] = float(len(row.get("failures", [])))
    return metrics


def _metric_direction(metric_name: str) -> str:
    higher_is_better = {"success_rate", "minimum_obstacle_distance", "final_stopped_duration"}
    absolute_lower_is_better = {"final_lateral_error", "final_longitudinal_error", "final_yaw_error"}
    if metric_name in higher_is_better:
        return "higher_is_better"
    if metric_name in absolute_lower_is_better:
        return "absolute_lower_is_better"
    return "lower_is_better"


def _percent_delta(baseline: float, delta: float) -> float | None:
    if abs(baseline) < 1e-9:
        return None
    return (delta / abs(baseline)) * 100.0


def _is_regression(baseline: float, value: float, direction: str) -> bool:
    if direction == "higher_is_better":
        return value < baseline * 0.95 - 1e-9
    if direction == "absolute_lower_is_better":
        return abs(value) > abs(baseline) * 1.05 + 1e-9
    return value > baseline * 1.05 + 1e-9


def _is_improvement(baseline: float, value: float, direction: str) -> bool:
    if direction == "higher_is_better":
        return value > baseline * 1.05 + 1e-9
    if direction == "absolute_lower_is_better":
        return abs(value) < abs(baseline) * 0.95 - 1e-9
    return value < baseline * 0.95 - 1e-9
