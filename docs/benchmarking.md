# Benchmarking

NavigationAnalyzer benchmark artifacts are JSON-first so they can be compared in CI, notebooks, and AI-agent workflows.

## Local Benchmark

```bash
navigation-analyzer benchmark \
  --bag examples/sample_bag/sample_navigation.json \
  --bag examples/nav2_sim_success_003/navigation_run.json \
  --config config/default.yaml \
  --thresholds config/benchmark_nav2.yaml \
  --report outputs/benchmark.md \
  --out outputs/benchmark.json
```

The output contains:

- `summary.run_count`
- `summary.metric_means`
- `summary.failure_type_counts`
- `thresholds.passed`
- `thresholds.violations`
- `comparisons.baseline_run_id`
- `comparisons.metric_deltas`
- per-run metrics
- per-run structured failure findings
- Markdown comparisons for best goal distance, shortest path, fastest goal reach, and fewest failures
- Markdown baseline diffs for metric regressions against the first run

The first `--bag` is treated as the baseline for `comparisons.metric_deltas`. Put your known-good run first when comparing candidate planners or parameter changes.

## CI Gate

Use `--fail-on-regression` to return a non-zero exit code when thresholds fail.

```bash
navigation-analyzer benchmark \
  --bag examples/nav2_sim_success_003/navigation_run.json \
  --config config/default.yaml \
  --thresholds config/benchmark_nav2.yaml \
  --report outputs/benchmark_nav2.md \
  --out outputs/benchmark_nav2.json \
  --fail-on-regression
```

## Goal Profiles

`config/benchmark_nav2.yaml` follows Nav2-style goal checking: require success, enforce XY goal tolerance, keep collision count zero, and block high-risk failure classes. Nav2 SimpleGoalChecker exposes `xy_goal_tolerance` and `yaw_goal_tolerance`, both defaulting to `0.25` in the current docs.

`config/benchmark_autoware.yaml` follows Autoware-style arrival checks: goal proximity, final stopped command, stopped duration, and no high-severity failures. Autoware Mission Planner documents arrival check parameters for angle, lateral distance, longitudinal undershoot/overshoot, and duration. Autoware's goal distance calculator publishes lateral, longitudinal, and yaw deviations from goal.

References:

- Nav2 SimpleGoalChecker: https://docs.nav2.org/configuration/packages/nav2_controller-plugins/simple_goal_checker.html
- Autoware Mission Planner: https://autowarefoundation.github.io/autoware_universe/main/planning/autoware_mission_planner_universe/
- Autoware goal distance calculator: https://autowarefoundation.github.io/autoware_universe/pr-10077/common/autoware_goal_distance_calculator/Readme/

## Regression Fixture

`examples/nav2_sim_success_003/navigation_run.json` is the first real-simulation-derived fixture. It is compacted from a Jazzy Nav2 TurtleBot3 bag and does not require ROS2 at test time.

Expected properties:

```text
success_rate = 1.0
time_to_goal ~= 3.744s
goal_distance ~= 0.181m
path_length ~= 0.721m
final_lateral_error ~= -0.058m
final_longitudinal_error ~= -0.171m
final_yaw_error ~= 0.191rad
final_stopped_duration ~= 17.388s
failure_types = ["narrow_passage_failure"]
```

## Raw Bag Policy

Raw ROS2 bags are ignored by git. Keep them under `bags/` for local validation. Commit compact canonical JSON exports under `examples/` only when they are small and useful for regression tests.

## GitHub Actions

The repository includes `.github/workflows/ci.yml` with:

- backend pytest
- Nav2 fixture benchmark gate
- frontend production build
- benchmark artifact upload
