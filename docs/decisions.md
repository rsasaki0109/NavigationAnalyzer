# Decisions

## D001: CLI is the primary product surface

The CLI owns analysis, benchmark, report, and serving commands. The frontend consumes generated artifacts instead of becoming the source of truth.

Reason: robotics debugging often runs in CI, remote machines, and batch simulation sweeps. CLI artifacts are reproducible and AI-readable.

## D002: Use a canonical schema between readers and analysis

All readers produce `NavigationRun`. All outputs consume `AnalysisArtifact`.

Reason: ROS2 topic layouts vary across Nav2, Autoware, research systems, and simulation environments. A canonical schema isolates that variance.

## D003: Keep MVP rules deterministic

Failure analysis starts rule-based.

Reason: deterministic evidence is easier to debug, benchmark, and improve incrementally. Later classifiers should augment, not replace, transparent rules.

## D004: Visualization is artifact-driven

The web app fetches `analysis.json` through FastAPI.

Reason: this makes screenshots, replay, and sharing depend on one portable artifact.

## D005: Avoid early plugin architecture

The MVP uses direct modules and functions.

Reason: plugin abstractions are premature until at least two real bag formats, two navigation stacks, or multiple metric implementations need side-by-side comparison.
