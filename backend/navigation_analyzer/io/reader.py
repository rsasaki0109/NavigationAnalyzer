from __future__ import annotations

import json
from pathlib import Path

from navigation_analyzer.io.rosbag2 import read_rosbag2
from navigation_analyzer.models import AnalyzerConfig, NavigationRun


def read_navigation_run(path: Path, config: AnalyzerConfig | None = None) -> NavigationRun:
    """Read a navigation run from ROS2 bag when possible, or JSON sample data.

    The JSON format is the canonical interchange format for tests, examples,
    and AI-agent workflows. ROS2 bag support maps bag topics into this schema.
    """

    if path.is_dir():
        for candidate in (
            path / "navigation_run.json",
            path / "sample_navigation.json",
            path / "analysis_input.json",
        ):
            if candidate.exists():
                return _read_json(candidate)
        return read_rosbag2(path, config)
    if path.suffix.lower() in {".json", ".jsonl"}:
        return _read_json(path)
    return read_rosbag2(path, config)


def _read_json(path: Path) -> NavigationRun:
    if path.suffix.lower() == ".jsonl":
        samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        payload = {
            "run_id": path.stem,
            "source": str(path),
            "samples": samples,
        }
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("source", str(path))
        payload.setdefault("run_id", path.stem)
    return NavigationRun.model_validate(payload)
