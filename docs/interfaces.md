# Interfaces

## CLI

### Analyze

```bash
navigation-analyzer analyze \
  --bag examples/sample_bag/sample_navigation.json \
  --config config/default.yaml \
  --out outputs/sample
```

Writes:

- `analysis.json`
- `report.md`

### Benchmark

```bash
navigation-analyzer benchmark \
  --bag run_a \
  --bag run_b \
  --config config/default.yaml \
  --out outputs/benchmark.json
```

Writes one JSON file with comparable run rows.

### Convert

```bash
navigation-analyzer convert \
  --bag run_a \
  --config config/default.yaml \
  --out outputs/navigation_run.json
```

Writes canonical `NavigationRun` JSON. This is the preferred bridge for AI agents and for debugging ROS2 topic extraction before metrics are evaluated.

### Serve

```bash
navigation-analyzer serve --analysis outputs/sample/analysis.json --port 8000
```

Endpoints:

- `GET /health`
- `GET /analysis`
- `GET /metrics`
- `GET /failures`
- `GET /diagnostics`

## Canonical Input

```json
{
  "run_id": "sample",
  "source": "sample.json",
  "goal": { "x": 5.0, "y": 0.0 },
  "goal_pose": { "x": 5.0, "y": 0.0, "yaw": 0.0 },
  "planned_path": [{ "x": 0.0, "y": 0.0 }],
  "samples": [
    {
      "t": 0.0,
      "pose": { "x": 0.0, "y": 0.0, "yaw": 0.0 },
      "cmd_v": 0.2,
      "cmd_w": 0.0,
      "goal_distance": 5.0,
      "obstacle_distance": 1.2,
      "collision": false,
      "recovery_event": false,
      "localization_error": 0.03
    }
  ]
}
```

## ROS2 Topic Mapping

Default topic names are configurable under `rosbag_topics` in `config/default.yaml`.

```yaml
rosbag_topics:
  tf: ["/tf"]
  localization_pose: ["/amcl_pose", "/pose", "/localization_pose"]
  odometry: ["/odom", "/odometry/filtered"]
  cmd_vel: ["/cmd_vel", "/cmd_vel_smoothed"]
  scan: ["/scan"]
  pointcloud: ["/points"]
  plan: ["/plan", "/global_plan"]
  trajectory: ["/local_plan", "/trajectory"]
  costmap: ["/global_costmap/costmap", "/local_costmap/costmap"]
  goal: ["/goal_pose"]
  recovery: ["/recoveries", "/recovery_status"]
```

If a configured topic is absent, the reader falls back to message-type discovery for common ROS2 message types such as `nav_msgs/msg/Odometry`, `geometry_msgs/msg/Twist`, `sensor_msgs/msg/LaserScan`, `sensor_msgs/msg/PointCloud2`, `nav_msgs/msg/Path`, and `nav_msgs/msg/OccupancyGrid`.

Use `config/autoware.yaml` for Autoware-oriented topic names. It maps common localization, control command, trajectory, pointcloud, and mission goal topics into the same canonical schema.

For Autoware `autoware_planning_msgs/msg/LaneletRoute`, NavigationAnalyzer stores route metadata in `run.metadata.route_summary`:

```json
{
  "segment_count": 2,
  "primitive_count": 2,
  "unique_primitive_count": 2,
  "preferred_ids": [9803, 127],
  "primitive_types": { "lane": 2 },
  "start_pose": { "x": 3810.3, "y": 73819.5, "z": 19.4, "yaw": 0.482 },
  "goal_pose": { "x": 3850.0, "y": 73840.0, "z": 19.1, "yaw": 0.482 }
}
```

## Analysis Output

```json
{
  "schema_version": "navigation-analyzer.analysis.v1",
  "run": {},
  "metrics": {
    "path_length": {
      "name": "path_length",
      "value": 12.3,
      "unit": "m",
      "description": "Integrated trajectory length from odometry poses."
    }
  },
  "failures": [
    {
      "failure_type": "oscillation",
      "timestamp": 123.4,
      "severity": "medium",
      "confidence": 0.78,
      "evidence": { "sign_changes": 6 },
      "possible_causes": [
        "local planner instability",
        "inflation radius too large"
      ]
    }
  ],
  "diagnostics": [
    {
      "diagnostic_type": "goal_reached_route_progress_mismatch",
      "timestamp": 42.0,
      "level": "warning",
      "confidence": 0.74,
      "summary": "Goal tolerance was satisfied before the matched lanelet route centerline was fully traversed.",
      "evidence": {
        "route_lanelet_progress_ratio": 0.79,
        "route_lanelet_remaining_distance_m": 14.0
      },
      "recommendations": [
        "Check whether the mission goal lies before the end of the final lanelet."
      ]
    }
  ]
}
```

## Metric System Design

Each metric is a pure function over `NavigationRun` plus `AnalyzerConfig`. Metric outputs include name, value, unit, and description.

Initial metrics:

| Metric | Meaning |
| --- | --- |
| `success_rate` | 1.0 if final goal distance is within tolerance, else 0.0 |
| `path_length` | integrated odometry trajectory length |
| `goal_distance` | final distance to goal |
| `time_to_goal` | first time within goal tolerance |
| `collision_count` | collision flag or obstacle-distance threshold crossings |
| `oscillation_count` | angular velocity sign changes during near-stationary rotation |
| `recovery_count` | recovery event count |
| `path_smoothness` | heading change per meter |
| `minimum_obstacle_distance` | closest observed obstacle |
| `final_lateral_error` | final cross-track error in goal frame |
| `final_longitudinal_error` | final along-track error in goal frame |
| `final_yaw_error` | final heading error relative to goal yaw |
| `final_stopped_duration` | final near-zero command duration |
| `route_progress_ratio` | final pose projected onto the Autoware route start-to-goal line |
| `route_straight_line_lateral_error` | signed final offset from the Autoware route start-to-goal line |
| `route_straight_line_remaining_distance` | remaining projected distance along the Autoware route start-to-goal line |
| `route_lanelet_centerline_distance` | final distance to the preferred route lanelet centerline from `lanelet2_map` |
| `route_lanelet_mean_centerline_distance` | mean sample distance to the preferred route lanelet centerline |
| `route_lanelet_max_centerline_distance` | maximum sample distance to the preferred route lanelet centerline |
| `route_lanelet_progress_ratio` | final projection progress along the matched preferred route lanelets |
| `route_lanelet_remaining_distance` | remaining centerline distance along matched preferred route lanelets |
| `route_lanelet_matched_count` | count of preferred route lanelets found in the configured map |

## Failure Taxonomy Design

Each failure has:

- `failure_type`
- `timestamp`
- `severity`
- `confidence`
- `evidence`
- `possible_causes`

Initial taxonomy:

| Failure | Rule signal |
| --- | --- |
| `localization_drift` | localization error crosses threshold |
| `oscillation` | repeated angular velocity sign changes within a window |
| `deadlock` | low commanded motion while still far from goal |
| `narrow_passage_failure` | low clearance and low forward speed |
| `dynamic_obstacle_freeze` | freeze near a non-contact obstacle |
| `planner_divergence` | trajectory moves far from planned path; Autoware route metadata is added to evidence when available |

For Autoware runs, `planner_divergence` evidence can include:

```json
{
  "planned_path_topic": "/planning/scenario_planning/trajectory",
  "route_topic": "/planning/mission_planning/route",
  "route_segment_count": 2,
  "route_primitive_count": 2,
  "route_preferred_ids": [9803, 127],
  "route_goal_distance_m": 48.7
}
```

## Diagnostic Design

Diagnostics are non-fatal structured warnings. They do not change `success_rate` and are separate from `FailureFinding`.

Initial diagnostics:

| Diagnostic | Signal |
| --- | --- |
| `goal_reached_route_progress_mismatch` | success is true, but lanelet route progress remains below the configured ratio with remaining centerline distance |
| `route_lanelet_deviation` | maximum distance to matched route lanelet centerline exceeds the configured warning threshold |

Benchmark profiles can optionally gate diagnostics with:

```yaml
diagnostics:
  max_count: 0
  max_level: info
  disallow_types:
    - goal_reached_route_progress_mismatch
```
