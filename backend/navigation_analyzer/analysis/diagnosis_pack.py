from __future__ import annotations

import math
from typing import Any

from navigation_analyzer.models import (
    AnalysisArtifact,
    DiagnosisOutcome,
    DiagnosisPack,
    DiagnosisRunSummary,
    EvidenceWindow,
    FailureFinding,
    Hypothesis,
    MetricResult,
    NavigationRun,
    NavigationSample,
    Pose2D,
    Severity,
)

_SEVERITY_RANK = {Severity.high: 3, Severity.medium: 2, Severity.low: 1}

_DEFAULT_WINDOW_HALF_S = 5.0

_FAILURE_TITLES = {
    "localization_drift": "Localization error grew beyond drift threshold",
    "oscillation": "Controller oscillated near stationary speed",
    "deadlock": "Robot stalled while still far from goal",
    "narrow_passage_failure": "Robot slowed in tight clearance and did not reach goal",
    "dynamic_obstacle_freeze": "Robot froze near a non-contact obstacle",
    "planner_divergence": "Trajectory diverged from the planned path",
    "tf_dropout": "TF chain stayed stale longer than the dropout threshold",
}


def build_diagnosis_pack(artifact: AnalysisArtifact) -> DiagnosisPack:
    run = artifact.run
    metrics = artifact.metrics
    samples = sorted(run.samples, key=lambda sample: sample.t)

    summary = _build_run_summary(run, samples)
    outcome = _build_outcome(artifact)

    failures_sorted = sorted(
        artifact.failures,
        key=lambda failure: (_SEVERITY_RANK.get(failure.severity, 0), failure.confidence),
        reverse=True,
    )

    evidence_windows: list[EvidenceWindow] = []
    hypotheses: list[Hypothesis] = []
    for index, failure in enumerate(failures_sorted, start=1):
        window = _build_evidence_window(index, failure, samples)
        hypothesis = _build_hypothesis(index, failure, window)
        evidence_windows.append(window)
        hypotheses.append(hypothesis)

    missing_signals = _detect_missing_signals(run, samples, metrics)

    return DiagnosisPack(
        run=summary,
        outcome=outcome,
        top_hypotheses=hypotheses,
        diagnostics=list(artifact.diagnostics),
        evidence_windows=evidence_windows,
        missing_signals=missing_signals,
    )


def _build_run_summary(run: NavigationRun, samples: list[NavigationSample]) -> DiagnosisRunSummary:
    duration_s = 0.0
    if samples:
        duration_s = max(0.0, samples[-1].t - samples[0].t)

    return DiagnosisRunSummary(
        run_id=run.run_id,
        source=run.source,
        source_type=_detect_source_type(run),
        profile=_detect_profile(run),
        duration_s=duration_s,
        sample_count=len(samples),
        goal=run.goal_pose if run.goal_pose is not None else _pose_from_point(run.goal),
    )


def _detect_source_type(run: NavigationRun) -> str:
    explicit = run.metadata.get("source_type")
    if isinstance(explicit, str):
        return explicit
    source = run.source.lower()
    if source.endswith(".json"):
        return "canonical_json"
    if source.endswith(".log"):
        return "unitree_log"
    if any(key in run.metadata for key in ("planned_path_topic", "route_topic", "bag_path")):
        return "ros2_bag"
    return "unknown"


def _detect_profile(run: NavigationRun) -> str | None:
    stack = run.metadata.get("stack")
    if isinstance(stack, str) and stack:
        return stack
    if "route_summary" in run.metadata or "route_topic" in run.metadata:
        return "autoware"
    if "planned_path_topic" in run.metadata:
        return "nav2"
    return None


def _pose_from_point(point) -> Pose2D | None:
    if point is None:
        return None
    return Pose2D(x=point.x, y=point.y, yaw=0.0)


def _build_outcome(artifact: AnalysisArtifact) -> DiagnosisOutcome:
    success_rate = _metric_number(artifact.metrics, "success_rate")
    failures = artifact.failures
    failure_count = len(failures)
    diagnostic_count = len(artifact.diagnostics)
    passed = (success_rate == 1.0) and failure_count == 0

    primary_failure: str | None = None
    if failures:
        ordered = sorted(
            failures,
            key=lambda failure: (_SEVERITY_RANK.get(failure.severity, 0), failure.confidence),
            reverse=True,
        )
        primary_failure = ordered[0].failure_type

    return DiagnosisOutcome(
        passed=passed,
        success_rate=success_rate,
        primary_failure=primary_failure,
        failure_count=failure_count,
        diagnostic_count=diagnostic_count,
    )


def _build_evidence_window(
    index: int,
    failure: FailureFinding,
    samples: list[NavigationSample],
) -> EvidenceWindow:
    window_id = f"win_{index:03d}"
    if not samples:
        return EvidenceWindow(
            id=window_id,
            t_start=failure.timestamp,
            t_end=failure.timestamp,
            reason=f"{failure.failure_type} reference timestamp",
            signals={},
        )
    t_start = max(samples[0].t, failure.timestamp - _DEFAULT_WINDOW_HALF_S)
    t_end = min(samples[-1].t, failure.timestamp + _DEFAULT_WINDOW_HALF_S)
    if t_end <= t_start:
        t_start = samples[0].t
        t_end = samples[-1].t

    window_samples = [sample for sample in samples if t_start <= sample.t <= t_end]
    if not window_samples:
        window_samples = [_closest_sample(samples, failure.timestamp)]
        t_start = window_samples[0].t
        t_end = window_samples[0].t

    return EvidenceWindow(
        id=window_id,
        t_start=t_start,
        t_end=t_end,
        reason=_window_reason(failure),
        signals=_summarize_signals(window_samples),
    )


def _window_reason(failure: FailureFinding) -> str:
    return f"{failure.failure_type} centered at t={failure.timestamp:.2f}s ({failure.severity.value})"


def _summarize_signals(samples: list[NavigationSample]) -> dict[str, Any]:
    if not samples:
        return {}

    cmd_v = [sample.cmd_v for sample in samples]
    cmd_w = [sample.cmd_w for sample in samples]
    goal_distances = [sample.goal_distance for sample in samples if sample.goal_distance is not None]
    obstacle_distances = [sample.obstacle_distance for sample in samples if sample.obstacle_distance is not None]
    localization_errors = [sample.localization_error for sample in samples if sample.localization_error is not None]

    pose_path_length = 0.0
    for previous, current in zip(samples, samples[1:]):
        pose_path_length += math.hypot(current.pose.x - previous.pose.x, current.pose.y - previous.pose.y)

    signals: dict[str, Any] = {
        "sample_count": len(samples),
        "pose_path_length_m": pose_path_length,
        "cmd_v": _stats(cmd_v),
        "cmd_w": _stats(cmd_w, include_sign_changes=True),
        "recovery_events": sum(1 for sample in samples if sample.recovery_event),
        "collision_samples": sum(1 for sample in samples if sample.collision),
    }
    if goal_distances:
        signals["goal_distance"] = _stats(goal_distances, include_trend=True)
    if obstacle_distances:
        signals["obstacle_distance"] = _stats(obstacle_distances)
    if localization_errors:
        signals["localization_error"] = _stats(localization_errors, include_trend=True)
    return signals


def _stats(
    values: list[float],
    include_sign_changes: bool = False,
    include_trend: bool = False,
) -> dict[str, Any]:
    if not values:
        return {}
    out: dict[str, Any] = {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }
    if include_sign_changes:
        out["sign_changes"] = sum(
            1
            for a, b in zip(values, values[1:])
            if (a > 0 and b < 0) or (a < 0 and b > 0)
        )
        out["max_abs"] = max(abs(value) for value in values)
    if include_trend:
        out["trend"] = _trend(values)
    return out


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "flat"
    delta = values[-1] - values[0]
    scale = max(1e-9, abs(values[0]), abs(values[-1]))
    ratio = delta / scale
    if ratio > 0.05:
        return "rising"
    if ratio < -0.05:
        return "falling"
    return "flat"


def _closest_sample(samples: list[NavigationSample], timestamp: float) -> NavigationSample:
    return min(samples, key=lambda sample: abs(sample.t - timestamp))


def _build_hypothesis(
    index: int,
    failure: FailureFinding,
    window: EvidenceWindow,
) -> Hypothesis:
    hypothesis_id = f"hyp_{index:03d}"
    title = _FAILURE_TITLES.get(failure.failure_type, failure.failure_type.replace("_", " "))
    observations = _observations_from_failure(failure)
    next_checks = _next_checks_from_causes(failure.possible_causes)
    return Hypothesis(
        id=hypothesis_id,
        title=title,
        confidence=failure.confidence,
        severity=failure.severity,
        supporting_observations=observations,
        alternative_causes=list(failure.possible_causes),
        next_checks=next_checks,
        evidence_window_ids=[window.id],
        source_failure_type=failure.failure_type,
        source_timestamp=failure.timestamp,
    )


def _observations_from_failure(failure: FailureFinding) -> list[str]:
    observations: list[str] = []
    for key, value in failure.evidence.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                observations.append(f"{key} is true")
            continue
        if isinstance(value, int | float):
            observations.append(f"{key} = {_format_number(value)}")
            continue
        if isinstance(value, str):
            observations.append(f"{key}: {value}")
            continue
        if isinstance(value, list):
            preview = ", ".join(str(item) for item in value[:5])
            suffix = "" if len(value) <= 5 else f", +{len(value) - 5} more"
            observations.append(f"{key}: [{preview}{suffix}]")
            continue
        observations.append(f"{key}: {value}")
    return observations


def _next_checks_from_causes(possible_causes: list[str]) -> list[str]:
    return [f"Inspect: {cause}" for cause in possible_causes]


def _format_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if abs(value) >= 100 or value == 0:
        return f"{value:.3f}"
    return f"{value:.4f}"


def _detect_missing_signals(
    run: NavigationRun,
    samples: list[NavigationSample],
    metrics: dict[str, MetricResult],
) -> list[str]:
    missing: list[str] = []
    if not samples:
        return ["samples"]
    if run.goal is None and run.goal_pose is None:
        missing.append("goal")
    if not run.planned_path:
        missing.append("planned_path")
    if run.costmap is None:
        missing.append("costmap")
    if all(sample.obstacle_distance is None for sample in samples):
        missing.append("obstacle_distance")
    if all(sample.localization_error is None for sample in samples):
        missing.append("localization_error")
    if all(sample.goal_distance is None for sample in samples):
        missing.append("goal_distance")
    if not any(sample.recovery_event for sample in samples) and "recovery_topic" not in run.metadata:
        missing.append("recovery_events")
    if "route_summary" not in run.metadata and _metric_number(metrics, "route_lanelet_matched_count") in (None, 0):
        missing.append("route_context")
    return missing


def _metric_number(metrics: dict[str, MetricResult], name: str) -> float | None:
    metric = metrics.get(name)
    value = metric.value if metric is not None else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
