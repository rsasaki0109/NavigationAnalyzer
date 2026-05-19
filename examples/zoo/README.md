# Failure Zoo

A gallery of small canonical fixtures, each tuned to exercise one rule in
NavigationAnalyzer. Use it to:

- See what `diagnosis.md` looks like across the failure taxonomy without running
  ROS2 or any simulation.
- Regression-protect changes to the analysis engine.
- Demo the difference between a *failure* (breaks `success_rate`) and a
  *diagnostic* (advisory warning).

Each subfolder commits two artifacts so GitHub viewers can browse them
directly:

- `navigation_run.json` — the canonical input fixture.
- `diagnosis.md` — the PR-comment-ready snapshot the analyzer produced.

## Index

| Fixture | Verdict | Primary failure | Diagnostics |
| --- | --- | --- | --- |
| [success_clean](success_clean/diagnosis.md) | **PASS** | — | — |
| [nav2_yaw_violation](nav2_yaw_violation/diagnosis.md) | **PASS** | — | `nav2_goal_tolerance_violation` (yaw) |
| [oscillation_near_goal](oscillation_near_goal/diagnosis.md) | **FAIL** | `oscillation` | `nav2_goal_tolerance_violation` (xy) |
| [deadlock](deadlock/diagnosis.md) | **FAIL** | `deadlock` | `nav2_goal_tolerance_violation` (xy) |
| [localization_drift](localization_drift/diagnosis.md) | **FAIL** | `localization_drift` | — |
| [dynamic_obstacle_freeze](dynamic_obstacle_freeze/diagnosis.md) | **FAIL** | `dynamic_obstacle_freeze` | — |
| [planner_divergence](planner_divergence/diagnosis.md) | **FAIL** | `planner_divergence` | — |

`nav2_yaw_violation` is the headline case for the Nav2 SimpleGoalChecker
auditor: `success_rate=1.0` (the run reached the goal by the analyzer's
default tolerance), but final yaw exceeds Nav2's `yaw_goal_tolerance`
default. The diagnostic surfaces a regression that would otherwise be
hidden by a lenient analyzer tolerance.

## Regenerate

```bash
scripts/run_failure_zoo.sh
```

The script:

1. Regenerates `navigation_run.json` from `examples/zoo/generate.py`.
2. Runs `navigation-analyzer analyze` on each fixture.
3. Writes `analysis.json`, `diagnosis_pack.json`, `report.md`, and
   `diagnosis.md` under `outputs/zoo/<name>/`.
4. Copies the new `diagnosis.md` back beside each fixture so the committed
   snapshot stays current.

After a behavior change in the analyzer (new metric, new failure rule,
new diagnostic, threshold tune), rerun the zoo and review the diff in
`examples/zoo/*/diagnosis.md` as part of the PR.
