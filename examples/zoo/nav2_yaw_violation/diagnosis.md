# Navigation Diagnosis: zoo_nav2_yaw_violation

**PASS** · success_rate=1 · 0 failures · 1 diagnostics

- Source: `examples/zoo/nav2_yaw_violation/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 10.00s · 11 samples

## Top Hypotheses

No top hypotheses — run passed all rule-based checks.

## Diagnostics

### `nav2_goal_tolerance_violation` — warning (confidence 0.80, t=10.00s)

Final pose violates Nav2 SimpleGoalChecker tolerance on yaw.

Evidence:
- axes_violated: [yaw]
- nav2_xy_goal_tolerance_m: 0.250
- nav2_yaw_goal_tolerance_rad: 0.250
- final_goal_distance_m: 0
- final_yaw_error_rad: 0.500
- xy_pass: true
- yaw_pass: false
- success_rate_at_audit: 1.000
- final_lateral_error_m: 0
- final_longitudinal_error_m: 0

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
