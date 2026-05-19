from __future__ import annotations

from typing import Any

from navigation_analyzer.models import DiagnosisPack, DiagnosticFinding, EvidenceWindow, Hypothesis


def render_diagnosis_markdown(pack: DiagnosisPack) -> str:
    """Render DiagnosisPack as a compact, PR-comment-ready Markdown summary."""

    windows_by_id = {window.id: window for window in pack.evidence_windows}

    lines: list[str] = []
    lines.append(f"# Navigation Diagnosis: {pack.run.run_id}")
    lines.append("")
    lines.extend(_render_header(pack))
    lines.append("")
    lines.extend(_render_meta(pack))
    lines.append("")
    lines.extend(_render_hypotheses(pack.top_hypotheses, windows_by_id))
    lines.extend(_render_diagnostics(pack.diagnostics))
    lines.extend(_render_missing_signals(pack.missing_signals))
    lines.append("")
    lines.append("---")
    lines.append("Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`")
    return "\n".join(lines).rstrip() + "\n"


def _render_header(pack: DiagnosisPack) -> list[str]:
    verdict = "PASS" if pack.outcome.passed else "FAIL"
    success_rate = pack.outcome.success_rate
    success_text = "n/a" if success_rate is None else f"{success_rate:g}"
    parts = [
        f"**{verdict}**",
        f"success_rate={success_text}",
        f"{pack.outcome.failure_count} failures",
        f"{pack.outcome.diagnostic_count} diagnostics",
    ]
    header_lines = [" · ".join(parts)]
    if pack.outcome.primary_failure:
        header_lines.append("")
        header_lines.append(f"Primary failure: `{pack.outcome.primary_failure}`")
    return header_lines


def _render_meta(pack: DiagnosisPack) -> list[str]:
    profile = pack.run.profile or "unknown"
    return [
        f"- Source: `{pack.run.source}` ({pack.run.source_type})",
        f"- Profile: `{profile}`",
        f"- Duration: {pack.run.duration_s:.2f}s · {pack.run.sample_count} samples",
    ]


def _render_hypotheses(
    hypotheses: list[Hypothesis],
    windows_by_id: dict[str, EvidenceWindow],
) -> list[str]:
    lines = ["## Top Hypotheses", ""]
    if not hypotheses:
        lines.append("No top hypotheses — run passed all rule-based checks.")
        lines.append("")
        return lines

    for index, hypothesis in enumerate(hypotheses, start=1):
        lines.append(f"### {index}. {hypothesis.title}  `{hypothesis.id}`")
        lines.append("")
        source_pieces = [
            f"**Confidence:** {hypothesis.confidence:.2f}",
            f"**Severity:** {hypothesis.severity.value}",
        ]
        if hypothesis.source_failure_type is not None and hypothesis.source_timestamp is not None:
            source_pieces.append(
                f"**Source:** {hypothesis.source_failure_type} @ t={hypothesis.source_timestamp:.2f}s"
            )
        lines.append(" · ".join(source_pieces))

        if hypothesis.supporting_observations:
            lines.append("")
            lines.append("Observations:")
            for observation in hypothesis.supporting_observations:
                lines.append(f"- {observation}")

        if hypothesis.alternative_causes:
            lines.append("")
            lines.append("Alternative causes: " + " · ".join(hypothesis.alternative_causes))

        if hypothesis.next_checks:
            lines.append("")
            lines.append("Next checks:")
            for check in hypothesis.next_checks:
                lines.append(f"- {check}")

        for window_id in hypothesis.evidence_window_ids:
            window = windows_by_id.get(window_id)
            if window is None:
                continue
            lines.append("")
            lines.append(
                f"Evidence window `{window.id}` (t={window.t_start:.2f}–{window.t_end:.2f}s):"
            )
            for signal_line in _summarize_window_signals(window.signals):
                lines.append(f"- {signal_line}")

        lines.append("")
    return lines


def _summarize_window_signals(signals: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not signals:
        return out
    sample_count = signals.get("sample_count")
    if isinstance(sample_count, int):
        out.append(f"sample_count: {sample_count}")
    for name in ("goal_distance", "localization_error", "obstacle_distance", "cmd_v"):
        stats = signals.get(name)
        if isinstance(stats, dict):
            out.append(_format_stats_line(name, stats))
    cmd_w = signals.get("cmd_w")
    if isinstance(cmd_w, dict):
        sign_changes = cmd_w.get("sign_changes")
        max_abs = cmd_w.get("max_abs")
        parts: list[str] = []
        if isinstance(sign_changes, int):
            parts.append(f"sign_changes={sign_changes}")
        if isinstance(max_abs, int | float):
            parts.append(f"max_abs={_fmt(max_abs)}")
        if parts:
            out.append("cmd_w: " + ", ".join(parts))
    recovery_events = signals.get("recovery_events")
    if isinstance(recovery_events, int) and recovery_events > 0:
        out.append(f"recovery_events: {recovery_events}")
    collision_samples = signals.get("collision_samples")
    if isinstance(collision_samples, int) and collision_samples > 0:
        out.append(f"collision_samples: {collision_samples}")
    return out


def _format_stats_line(name: str, stats: dict[str, Any]) -> str:
    pieces: list[str] = []
    trend = stats.get("trend")
    if isinstance(trend, str):
        pieces.append(f"trend={trend}")
    for key in ("min", "max", "mean"):
        value = stats.get(key)
        if isinstance(value, int | float):
            pieces.append(f"{key}={_fmt(value)}")
    return f"{name}: " + ", ".join(pieces)


def _render_diagnostics(diagnostics: list[DiagnosticFinding]) -> list[str]:
    if not diagnostics:
        return []
    lines = ["## Diagnostics", ""]
    for diagnostic in diagnostics:
        lines.append(
            f"### `{diagnostic.diagnostic_type}` — {diagnostic.level.value} "
            f"(confidence {diagnostic.confidence:.2f}, t={diagnostic.timestamp:.2f}s)"
        )
        lines.append("")
        lines.append(diagnostic.summary)
        evidence_lines = _summarize_diagnostic_evidence(diagnostic.evidence)
        if evidence_lines:
            lines.append("")
            lines.append("Evidence:")
            for evidence_line in evidence_lines:
                lines.append(f"- {evidence_line}")
        if diagnostic.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for recommendation in diagnostic.recommendations:
                lines.append(f"- {recommendation}")
        lines.append("")
    return lines


def _summarize_diagnostic_evidence(evidence: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key, value in evidence.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out.append(f"{key}: {str(value).lower()}")
            continue
        if isinstance(value, int):
            out.append(f"{key}: {value}")
            continue
        if isinstance(value, float):
            out.append(f"{key}: {_fmt(value)}")
            continue
        if isinstance(value, str):
            out.append(f"{key}: {value}")
            continue
        if isinstance(value, list):
            preview = ", ".join(str(item) for item in value[:5])
            suffix = "" if len(value) <= 5 else f", +{len(value) - 5} more"
            out.append(f"{key}: [{preview}{suffix}]")
            continue
        out.append(f"{key}: {value}")
    return out


def _render_missing_signals(missing_signals: list[str]) -> list[str]:
    if not missing_signals:
        return []
    lines = ["## Missing Signals", ""]
    for signal in missing_signals:
        lines.append(f"- {signal}")
    return lines


def _fmt(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0"
    if abs(value) >= 100:
        return f"{value:.2f}"
    return f"{value:.3f}"
