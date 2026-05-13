from __future__ import annotations

import json
from pathlib import Path

import yaml

from navigation_analyzer.models import AnalyzerConfig


def load_config(path: Path | None) -> AnalyzerConfig:
    if path is None:
        return AnalyzerConfig()
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    return AnalyzerConfig.model_validate(data or {})
