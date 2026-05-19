# Navigation Diagnosis: zoo_deadlock

**FAIL** · success_rate=0 · 1 failures · 1 diagnostics

Primary failure: `deadlock`

- Source: `examples/zoo/deadlock/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 21.00s · 21 samples

## Top Hypotheses

### 1. Robot stalled while still far from goal  `hyp_001`

**Confidence:** 0.74 · **Severity:** high · **Source:** deadlock @ t=5.00s

Observations:
- duration_s = 8.0000
- goal_distance_m = 8.0000

Alternative causes: blocked local costmap · planner/controller disagreement · recovery behavior loop

Next checks:
- Inspect: blocked local costmap
- Inspect: planner/controller disagreement
- Inspect: recovery behavior loop

Evidence window `win_001` (t=0.00–10.00s):
- sample_count: 10
- goal_distance: trend=falling, min=8.000, max=10.000, mean=8.600
- localization_error: trend=flat, min=0.050, max=0.050, mean=0.050
- obstacle_distance: min=1.500, max=1.500, mean=1.500
- cmd_v: min=0, max=0.400, mean=0.200
- cmd_w: sign_changes=0, max_abs=0

## Diagnostics

### `nav2_goal_tolerance_violation` — warning (confidence 0.80, t=21.00s)

Final pose violates Nav2 SimpleGoalChecker tolerance on xy.

Evidence:
- axes_violated: [xy]
- nav2_xy_goal_tolerance_m: 0.250
- nav2_yaw_goal_tolerance_rad: 0.250
- final_goal_distance_m: 8.000
- final_yaw_error_rad: 0
- xy_pass: false
- yaw_pass: true
- success_rate_at_audit: 0
- final_lateral_error_m: 0
- final_longitudinal_error_m: -8.000

Recommendations:
- Compare analyzer goal_tolerance_m with Nav2 SimpleGoalChecker xy_goal_tolerance and yaw_goal_tolerance.
- If success_rate is 1.0 but axes_violated is non-empty, the analyzer tolerance is more lenient than Nav2's; tighten it for CI.
- Inspect controller angular saturation and goal yaw target when yaw violations recur.

## Missing Signals

- costmap
- recovery_events
- route_context

---
Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`
