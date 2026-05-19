# Navigation Diagnosis: zoo_planner_divergence

**FAIL** · success_rate=1 · 1 failures · 0 diagnostics

Primary failure: `planner_divergence`

- Source: `examples/zoo/planner_divergence/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 10.00s · 21 samples

## Top Hypotheses

### 1. Trajectory diverged from the planned path  `hyp_001`

**Confidence:** 0.70 · **Severity:** high · **Source:** planner_divergence @ t=5.00s

Observations:
- max_distance_from_plan_m = 2.5000

Alternative causes: stale global plan · controller tracking failure · unexpected obstacle forcing detour

Next checks:
- Inspect: stale global plan
- Inspect: controller tracking failure
- Inspect: unexpected obstacle forcing detour

Evidence window `win_001` (t=0.00–10.00s):
- sample_count: 21
- goal_distance: trend=falling, min=0, max=10.000, mean=5.220
- localization_error: trend=flat, min=0.050, max=0.050, mean=0.050
- obstacle_distance: min=1.400, max=1.400, mean=1.400
- cmd_v: min=0, max=0.600, mean=0.571
- cmd_w: sign_changes=0, max_abs=0

## Missing Signals

- costmap
- recovery_events
- route_context

---
Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`
