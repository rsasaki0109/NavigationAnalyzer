from __future__ import annotations

from navigation_analyzer.models import AnalysisArtifact


def render_markdown_report(artifact: AnalysisArtifact) -> str:
    metrics = artifact.metrics
    lines = [
        f"# Navigation Analysis Report: {artifact.run.run_id}",
        "",
        "## Summary",
        "",
        f"- Source: `{artifact.run.source}`",
        f"- Samples: {len(artifact.run.samples)}",
        f"- Success: {metrics['success_rate'].value}",
        f"- Failure findings: {len(artifact.failures)}",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Unit |",
        "| --- | ---: | --- |",
    ]
    for metric in metrics.values():
        lines.append(f"| {metric.name} | {metric.value} | {metric.unit} |")

    route_summary = artifact.run.metadata.get("route_summary")
    if isinstance(route_summary, dict):
        lines.extend(["", "## Route Summary", ""])
        lines.append(f"- Topic: `{artifact.run.metadata.get('route_topic')}`")
        lines.append(f"- Timestamp: {artifact.run.metadata.get('route_time')}")
        lines.append(f"- Segments: {route_summary.get('segment_count')}")
        lines.append(f"- Primitives: {route_summary.get('primitive_count')}")
        lines.append(f"- Unique primitives: {route_summary.get('unique_primitive_count')}")
        primitive_types = route_summary.get("primitive_types")
        if primitive_types:
            lines.append(f"- Primitive types: `{primitive_types}`")
        preferred_ids = route_summary.get("preferred_ids")
        if preferred_ids:
            preview = ", ".join(str(value) for value in preferred_ids[:20])
            suffix = "..." if len(preferred_ids) > 20 else ""
            lines.append(f"- Preferred lanelet IDs: {preview}{suffix}")
        start_pose = route_summary.get("start_pose")
        goal_pose = route_summary.get("goal_pose")
        if start_pose:
            lines.append(f"- Route start: x={start_pose.get('x'):.3f}, y={start_pose.get('y'):.3f}, yaw={start_pose.get('yaw'):.3f}")
        if goal_pose:
            lines.append(f"- Route goal: x={goal_pose.get('x'):.3f}, y={goal_pose.get('y'):.3f}, yaw={goal_pose.get('yaw'):.3f}")

    lines.extend(["", "## Failure Findings", ""])
    if not artifact.failures:
        lines.append("No rule-based failures detected.")
    else:
        for finding in artifact.failures:
            causes = ", ".join(finding.possible_causes)
            lines.extend(
                [
                    f"### {finding.failure_type}",
                    "",
                    f"- Timestamp: {finding.timestamp:.3f}s",
                    f"- Severity: {finding.severity.value}",
                    f"- Confidence: {finding.confidence:.2f}",
                    f"- Evidence: `{finding.evidence}`",
                    f"- Possible causes: {causes}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
