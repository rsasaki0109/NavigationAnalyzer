# Architecture

NavigationAnalyzer is designed around a small canonical data model rather than around a UI or ROS message type. This keeps the CLI, reports, API, and web app aligned.

## Goals

- CLI first.
- AI-agent friendly structured output.
- ROS2 native ingestion.
- Reproducible benchmark artifacts.
- Visualization-heavy debugging.
- Minimal abstractions until repeated experiments justify them.

## Current Data Flow

```text
ROS2 bag or canonical JSON
        |
        v
NavigationRun
        |
        +--> metrics engine ------+
        |                         |
        +--> failure rules -------+--> AnalysisArtifact
        |                         |
        +--> diagnostics ---------+
                                      |
                                      +--> analysis.json
                                      +--> report.md
                                      +--> FastAPI
                                      +--> React visualization
```

## Backend Modules

- `navigation_analyzer.models`: Pydantic schemas for runs, metrics, failures, and artifacts.
- `navigation_analyzer.io.reader`: input dispatch for canonical JSON and future ROS2 bags.
- `navigation_analyzer.io.rosbag2`: ROS2 adapter scaffold.
- `navigation_analyzer.analysis.metrics`: deterministic metric functions.
- `navigation_analyzer.analysis.failures`: rule-based failure taxonomy.
- `navigation_analyzer.analysis.diagnostics`: non-fatal evaluation warnings.
- `navigation_analyzer.reporting.markdown`: compact AI-readable report.
- `navigation_analyzer.api.app`: local artifact server.
- `navigation_analyzer.cli.main`: Typer command surface.

## Frontend Modules

- `TrajectoryScene`: Three.js trajectory, plan, replay marker, and failure points.
- `MetricDashboard`: Plotly metric profile and obstacle-distance heatmap.
- `FailureTimeline`: replay control and failure jump list.

## ROS2 Bag Strategy

The MVP keeps the reader boundary explicit. Real ROS2 support should map common topics into `NavigationRun`:

| ROS2 source | Canonical field |
| --- | --- |
| `/odom` | odom-frame fallback pose and trajectory |
| `/tf`, especially `map -> odom -> base_footprint` | map-frame trajectory for goal-distance metrics |
| `/cmd_vel` | sample `cmd_v`, `cmd_w` |
| Autoware `autoware_control_msgs/msg/Control` | command velocity and steering proxy |
| `/tf_static` | static frame context |
| `/scan`, `/points` | obstacle distance |
| `/plan`, `/local_plan` | planned path |
| Autoware `autoware_planning_msgs/msg/Trajectory` | planned path from trajectory points |
| Autoware `autoware_planning_msgs/msg/LaneletRoute` | route metadata for route-aware failure evidence |
| lanelet2 OSM map | preferred route lanelet centerlines for map-aware metrics |
| costmap topics | costmap grid |
| `/goal_pose` | `goal_pose` with x/y/yaw for Nav2-style final error metrics |
| recovery/status topics | recovery events and task state |

The canonical model is the contract. ROS message extraction can evolve without breaking downstream consumers.
