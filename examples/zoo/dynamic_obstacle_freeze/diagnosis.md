# Navigation Diagnosis: zoo_dynamic_obstacle_freeze

**FAIL** · success_rate=1 · 1 failures · 0 diagnostics

Primary failure: `dynamic_obstacle_freeze`

- Source: `examples/zoo/dynamic_obstacle_freeze/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 21.00s · 22 samples

## Top Hypotheses

### 1. Robot froze near a non-contact obstacle  `hyp_001`

**Confidence:** 0.61 · **Severity:** medium · **Source:** dynamic_obstacle_freeze @ t=6.00s

Observations:
- samples = 5
- first_obstacle_distance_m = 0.4000

Alternative causes: obstacle persistence too long · velocity obstacle over-conservative · scene not clearing in costmap

Next checks:
- Inspect: obstacle persistence too long
- Inspect: velocity obstacle over-conservative
- Inspect: scene not clearing in costmap

Evidence window `win_001` (t=1.00–11.00s):
- sample_count: 11
- goal_distance: trend=falling, min=7.000, max=9.400, mean=7.545
- localization_error: trend=flat, min=0.050, max=0.050, mean=0.050
- obstacle_distance: min=0.400, max=1.200, mean=0.836
- cmd_v: min=0, max=0.700, mean=0.336
- cmd_w: sign_changes=0, max_abs=0

## Missing Signals

- costmap
- recovery_events
- route_context

---
Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`
