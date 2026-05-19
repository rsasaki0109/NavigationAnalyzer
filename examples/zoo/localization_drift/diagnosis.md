# Navigation Diagnosis: zoo_localization_drift

**FAIL** · success_rate=1 · 1 failures · 0 diagnostics

Primary failure: `localization_drift`

- Source: `examples/zoo/localization_drift/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 10.00s · 11 samples

## Top Hypotheses

### 1. Localization error grew beyond drift threshold  `hyp_001`

**Confidence:** 0.82 · **Severity:** medium · **Source:** localization_drift @ t=10.00s

Observations:
- localization_error_m = 0.8500

Alternative causes: poor scan matching · map mismatch · insufficient odometry fusion

Next checks:
- Inspect: poor scan matching
- Inspect: map mismatch
- Inspect: insufficient odometry fusion

Evidence window `win_001` (t=5.00–10.00s):
- sample_count: 6
- goal_distance: trend=falling, min=0, max=2.500, mean=1.250
- localization_error: trend=rising, min=0.450, max=0.850, mean=0.650
- obstacle_distance: min=1.500, max=1.500, mean=1.500
- cmd_v: min=0, max=0.500, mean=0.417
- cmd_w: sign_changes=0, max_abs=0

## Missing Signals

- costmap
- recovery_events
- route_context

---
Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`
