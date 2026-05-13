from __future__ import annotations

from navigation_analyzer.analysis.failures import detect_failures
from navigation_analyzer.analysis.metrics import compute_metrics
from navigation_analyzer.models import AnalysisArtifact, AnalyzerConfig, NavigationRun


def analyze_run(run: NavigationRun, config: AnalyzerConfig | None = None) -> AnalysisArtifact:
    resolved_config = config or AnalyzerConfig()
    metrics = compute_metrics(run, resolved_config)
    failures = detect_failures(run, resolved_config)
    return AnalysisArtifact(run=run, metrics=metrics, failures=failures)
