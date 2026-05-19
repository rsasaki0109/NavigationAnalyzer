# Navigation Diagnosis: zoo_oscillation_near_goal

**FAIL** · success_rate=0 · 1 failures · 1 diagnostics

Primary failure: `oscillation`

- Source: `examples/zoo/oscillation_near_goal/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 20.00s · 21 samples

## Top Hypotheses

### 1. Controller oscillated near stationary speed  `hyp_001`

**Confidence:** 0.78 · **Severity:** medium · **Source:** oscillation @ t=11.00s

Observations:
- sign_changes = 6
- window_s = 6.0000

Alternative causes: local planner instability · inflation radius too large · goal checker tolerance too strict

Next checks:
- Inspect: local planner instability
- Inspect: inflation radius too large
- Inspect: goal checker tolerance too strict

Evidence window `win_001` (t=6.00–16.00s):
- sample_count: 11
- goal_distance: trend=falling, min=1.000, max=2.600, mean=1.364
- localization_error: trend=flat, min=0.050, max=0.050, mean=0.050
- obstacle_distance: min=1.400, max=1.400, mean=1.400
- cmd_v: min=0.060, max=0.400, mean=0.184
- cmd_w: sign_changes=5, max_abs=0.450

## Diagnostics

### `nav2_goal_tolerance_violation` — warning (confidence 0.80, t=20.00s)

Final pose violates Nav2 SimpleGoalChecker tolerance on xy.

Evidence:
- axes_violated: [xy]
- nav2_xy_goal_tolerance_m: 0.250
- nav2_yaw_goal_tolerance_rad: 0.250
- final_goal_distance_m: 1.000
- final_yaw_error_rad: -0.250
- xy_pass: false
- yaw_pass: true
- success_rate_at_audit: 0
- final_lateral_error_m: 0
- final_longitudinal_error_m: -1.000

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
