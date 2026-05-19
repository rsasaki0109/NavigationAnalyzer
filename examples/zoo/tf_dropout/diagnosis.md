# Navigation Diagnosis: zoo_tf_dropout

**FAIL** · success_rate=1 · 1 failures · 0 diagnostics

Primary failure: `tf_dropout`

- Source: `examples/zoo/tf_dropout/navigation_run.json` (canonical_json)
- Profile: `nav2`
- Duration: 10.00s · 21 samples

## Top Hypotheses

### 1. TF chain stayed stale longer than the dropout threshold  `hyp_001`

**Confidence:** 0.78 · **Severity:** medium · **Source:** tf_dropout @ t=4.00s

Observations:
- tf_dropout_age_s = 0.5000
- tf_dropout_sustained_s = 1.0000
- window_start_s = 4.0000
- window_end_s = 7.0000
- window_duration_s = 3.0000
- peak_tf_age_s = 0.8500

Alternative causes: amcl or localization node stopped publishing map->odom · robot_state_publisher stalled (odom->base_link gap) · system clock skew between TF publisher and consumer · DDS network drop or QoS mismatch

Next checks:
- Inspect: amcl or localization node stopped publishing map->odom
- Inspect: robot_state_publisher stalled (odom->base_link gap)
- Inspect: system clock skew between TF publisher and consumer
- Inspect: DDS network drop or QoS mismatch

Evidence window `win_001` (t=0.00–9.00s):
- sample_count: 19
- goal_distance: trend=falling, min=0.500, max=5.000, mean=2.750
- localization_error: trend=flat, min=0.050, max=0.050, mean=0.050
- obstacle_distance: min=1.400, max=1.400, mean=1.400
- cmd_v: min=0.500, max=0.500, mean=0.500
- cmd_w: sign_changes=0, max_abs=0

## Missing Signals

- costmap
- recovery_events
- route_context

---
Full artifacts: `analysis.json`, `diagnosis_pack.json`, `report.md`
