# Experiments

This file is the project memory for implementation experiments. Add entries whenever a design is tried, compared, rejected, or adopted.

## 2026-05-12: Canonical JSON first

### Tried

Start with a canonical JSON reader and a ROS2 bag adapter scaffold.

### Benefits

- Works without a sourced ROS2 environment.
- Easy to test in CI.
- Easy for AI agents to inspect, generate, and diff.
- Allows frontend and report work to proceed before raw bag extraction is complete.

### Tradeoffs

- Real ROS2 bag users need the adapter finished.
- Some metrics are derived from already-extracted fields instead of raw sensor messages.

### Decision

Adopted for MVP. The project needs an end-to-end artifact path before investing in topic-specific extraction.

### Benchmark Results

Sample run:

```text
sample_nav2_failure_001: success=0.0, path=~1.63m, rule-based failures detected
```

## 2026-05-12: Rule-based failure taxonomy

### Tried

Implement deterministic rules for localization drift, oscillation, deadlock, narrow passage failure, dynamic obstacle freeze, and planner divergence.

### Benefits

- Transparent evidence.
- Stable benchmark output.
- Good first layer before ML/LLM classification.

### Tradeoffs

- Threshold-sensitive.
- Requires scenario-specific tuning.
- Can miss failures that require semantic context.

### Decision

Adopted. Keep every finding structured with timestamp, severity, confidence, evidence, and possible causes.

## 2026-05-12: ROS2 bag adapter with dynamic imports

### Tried

Implement `rosbag2_py` extraction behind the reader boundary while keeping imports dynamic.

### Benefits

- Non-ROS development and CI still work.
- ROS2 users can source a ROS environment and read real bags.
- Topic names are configurable, with message-type fallback for common Nav2 layouts.
- `convert` gives a quick way to inspect canonical data before running metrics.

### Tradeoffs

- PointCloud2 support depends on optional `sensor_msgs_py`.
- Recovery event parsing is topic-presence based in this iteration.
- Autoware-specific control commands need additional adapters.

### Decision

Adopted as the next MVP step. It keeps the platform end-to-end while creating a concrete path for real bag fixtures.

## 2026-05-12: Simulation-generated bags as first real fixtures

### Tried

Use TurtleBot3 + Nav2 simulation as the first source of real ROS2 bags.

### Benefits

- Reproducible enough for contributors.
- Uses standard Nav2 topics.
- Small bags can exercise `/odom`, `/cmd_vel`, `/scan`, plan, and costmap extraction.
- Failure scenarios can be created without hardware risk.

### Tradeoffs

- Requires a local ROS2 desktop/simulation environment.
- Gazebo/TurtleBot3 package names vary slightly by ROS2 distro.
- Simulation failures are not fully representative of hardware timing, wheel slip, sensor noise, or localization drift.

### Decision

Adopted for initial real-bag validation. Keep raw bags out of git; commit only small canonical JSON exports when they are stable regression fixtures.

### Validation Notes

Local Jazzy simulation produced:

```text
bags/nav2_sim_success_002: 29.3s, 2805 messages, success=1.0, failures=0
bags/nav2_sim_success_003: 44.0s, 4161 messages, success=1.0, failures=1
```

Lessons:

- `/goal_pose` must be published more than once or the recorder can miss it.
- `/odom` is not in the same frame as a Nav2 `map` goal; use `/tf` to compose `map -> odom -> base_footprint`.
- `/amcl_pose` can be too sparse for smooth trajectory metrics, so TF-derived poses are preferred when available.

## 2026-05-12: Compact canonical fixture from real simulation

### Tried

Commit a compact `NavigationRun` JSON derived from `bags/nav2_sim_success_003` instead of committing the raw bag.

### Benefits

- Keeps the repository small.
- Exercises real Nav2-derived geometry without requiring ROS in tests.
- Preserves success metrics and a narrow-passage warning for regression coverage.

### Tradeoffs

- Does not test `rosbag2_py` extraction in CI.
- Costmap payload was removed from the fixture to reduce size.
- Compaction can slightly change path length and smoothness.

### Decision

Adopted. Use raw bags locally for ROS adapter validation and compact canonical JSON in git for deterministic tests.

### Benchmark Results

```text
nav2_sim_success_003 compact fixture:
  success_rate = 1.0
  time_to_goal ~= 3.744s
  path_length ~= 0.721m
  failure_types = ["narrow_passage_failure"]
```

## 2026-05-13: Benchmark thresholds and stack profiles

### Tried

Add configurable benchmark thresholds with `generic`, `nav2`, and `autoware` profiles.

### Benefits

- Supports CI gating via `--fail-on-regression`.
- Produces Markdown benchmark reports.
- Encodes Nav2-style XY goal tolerance and Autoware-style stopped-duration checks without hard-coding one stack's semantics into core metrics.

### Tradeoffs

- Yaw goal tolerance is configured but not fully evaluated until the canonical schema carries goal yaw.
- Autoware lateral/longitudinal/yaw deviations are approximated by current generic metrics until Autoware route and deviation topics are parsed.

### Decision

Adopted. Keep profile configs explicit and use them as the bridge from stack-specific goal semantics to reproducible benchmark gates.

## 2026-05-13: Goal-pose-aware final error metrics

### Tried

Extend the canonical schema with `goal_pose` and compute final lateral, longitudinal, yaw, and stopped-duration metrics.

### Benefits

- Nav2 `yaw_goal_tolerance` can now be evaluated against `final_yaw_error`.
- Autoware-style lateral/longitudinal/yaw arrival checks have explicit metrics.
- Older fixtures with `goal` only remain valid through schema aliasing.

### Tradeoffs

- Autoware route-specific longitudinal semantics still need richer route/trajectory context.
- Current lateral/longitudinal errors are goal-heading-frame errors, not lanelet-aware deviations.

### Decision

Adopted. This is the correct intermediate contract before adding Autoware-specific readers.

## 2026-05-13: CI and Autoware topic profile

### Tried

Add GitHub Actions CI, `config/autoware.yaml`, Autoware control-command extraction, Autoware trajectory extraction, and benchmark comparison summaries.

### Benefits

- The repository can gate fixture regressions automatically.
- Autoware users have a starting topic map without changing code.
- Benchmark Markdown is easier to scan across multiple runs.

### Tradeoffs

- Autoware support is still topic-level MVP, not full route/lanelet semantic evaluation.
- Control command steering is stored in `cmd_w` as a proxy until the canonical schema grows a vehicle-control field.

### Decision

Adopted. It moves the project toward beta usability while keeping the canonical schema stable.

## 2026-05-13: Autoware Docker runtime as first install route

### Tried

Install Autoware through the official Docker runtime image:

```text
ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0
```

Also cloned `autowarefoundation/autoware` at tag `1.8.0` into `~/autoware` and downloaded the planning simulator sample map into `~/autoware_data/maps/sample-map-planning`.

### Benefits

- Avoids a multi-hour source build for the first Autoware validation loop.
- Matches the local Ubuntu 24.04 + ROS 2 Jazzy environment.
- Lets NavigationAnalyzer record bags from the same container that owns the Autoware message definitions.
- Keeps the source-install path open for later package-level development.

### Tradeoffs

- Host ROS 2 does not currently have Autoware message packages, so direct host-side conversion of Autoware bags is blocked until an Autoware workspace is sourced or message packages are installed.
- Docker image default CycloneDDS config uses `lo`; this host needs an `eth0` override because loopback multicast is disabled.
- Planning simulator needs RViz interaction or AD API goal publishing before it produces meaningful route/trajectory bags.

### Decision

Adopted for the next MVP loop. Use Docker for repeatable Autoware launch/record workflows, then add either host message packages or an analyzer-in-container entrypoint.

### Validation Notes

```text
Autoware image pull: ok
autoware_launch package in container: ok
planning_simulator.launch.xml rviz:=false: starts map/planning/control/perception dummy nodes
sample map: downloaded, 28M
record helper: writes MCAP bags from inside container
```

## 2026-05-13: Analyzer-in-container for Autoware bags

### Tried

Build a small derived image from the official Autoware runtime and run NavigationAnalyzer inside it:

```text
navigation-analyzer-autoware:jazzy-1.8.0
```

Added:

- `docker/autoware-analyzer/Dockerfile`
- `scripts/analyze_autoware_bag_docker.sh`
- `scripts/create_autoware_fixture_bag_docker.sh`

### Benefits

- Raw Autoware bags can be decoded without installing Autoware message packages on the host.
- The same image contains `rosbag2_py`, Autoware message definitions, and NavigationAnalyzer CLI dependencies.
- The fixture generator creates a tiny MCAP bag with `autoware_control_msgs/msg/Control` and `autoware_planning_msgs/msg/Trajectory`, which directly tests Autoware adapter paths.

### Tradeoffs

- Requires a local Docker build for the analyzer image.
- The derived image installs Python dependencies with pip on top of the runtime image; a published image would be cleaner later.
- Generated raw bags remain local artifacts and are not committed.

### Decision

Adopted for the Autoware MVP path. Keep host-native analysis for canonical JSON and Nav2, and use Docker analysis for raw Autoware bags until the project publishes binary/runtime packages.

### Benchmark Results

```text
autoware_fixture_success_001:
  messages = 20
  success_rate = 1.0
  path_length = 3.0 m
  goal_distance = 0.0 m
  final_stopped_duration = 3.0 s
  failures = 0
  benchmark_autoware = passed
```

## 2026-05-13: Headless Autoware planning simulator run

### Tried

Automate the official planning simulator flow in Docker without RViz:

- Launch `planning_simulator.launch.xml` with `use_sim_time:=false`.
- Publish the initial pose to both `/initialpose` and `/initialpose3d`.
- Set a route with `/api/routing/set_route_points`.
- Request autonomous mode and engage through AD API services.
- Record the selected navigation topics into `bags/autoware_planning_success_001`.

Default sample-map route:

```text
initial: x=3810.3 y=73819.5 z=19.4 yaw=0.482
goal:    x=3850.0 y=73840.0 z=19.4 yaw=0.482
```

### Benefits

- Creates a real Autoware bag from a reproducible CLI-only workflow.
- Does not require RViz interaction, which makes it usable by AI agents and CI-like runners.
- Exercises localization, route, trajectory, control command, velocity status, and Autoware state topics.
- Produces a bag that can be analyzed inside the derived Autoware analyzer image.

### Tradeoffs

- Autoware logs are noisy in headless mode because empty dummy pointcloud paths emit repeated PCL warnings.
- `ros2 bag record` can be slow to exit on SIGINT in this container, so the record script uses TERM/KILL fallback after giving it time to close.
- The first autonomous-mode request can return unavailable while diagnostics settle; the simulator still transitions to driving after route and state updates.

### Decision

Adopted as the first real Autoware simulator fixture workflow. Keep the raw bag local and commit only scripts, docs, and generated canonical outputs when they are small enough.

Also changed planner-divergence analysis for ROS2 bags to honor `metadata.planned_path_time`. Autoware's scenario trajectory is a rolling local trajectory, so comparing the final trajectory against the whole run produced a false high-severity `planner_divergence` at the starting pose.

### Benchmark Results

```text
autoware_planning_success_001:
  samples = 6346
  success_rate = 1.0
  path_length = 44.708 m
  goal_distance = 0.026 m
  final_lateral_error = 0.003 m
  final_longitudinal_error = 0.026 m
  final_yaw_error = -0.004 rad
  final_stopped_duration = 140.926 s
  failures = 0
  benchmark_autoware = passed
```

## 2026-05-13: Autoware-scale web visualization framing

### Tried

Load `outputs/autoware_planning_success_001/analysis.json` in the React/Three.js UI and verify the scene with Playwright screenshots.

### Benefits

- The trajectory scene now auto-fits the camera to sample, plan, goal, and costmap bounds instead of assuming small Nav2 coordinates.
- Start, finish, and goal markers make success runs readable even when there are no failures.
- A Playwright check captures desktop and mobile screenshots and verifies that the WebGL canvas has non-background pixels.

### Tradeoffs

- The WebGL renderer uses `preserveDrawingBuffer` so pixel checks are stable; this can have a rendering performance cost on very large scenes.
- Plotly still dominates the production bundle size. This is acceptable for the MVP, but lazy loading Plotly is a good later optimization.

### Decision

Adopted. Real Autoware map-frame coordinates must be a first-class visualization case, not a special case handled by manual zoom.

### Validation

```text
npm run build: passed
npm run check:visualization:
  desktop canvas unique colors = 20, non-background samples = 1089
  mobile canvas unique colors = 15, non-background samples = 689
```

## 2026-05-13: Multi-run benchmark dashboard

### Tried

Add a frontend dashboard that loads `benchmark.json` from the file picker and renders:

- run summary cards
- grouped metric bars
- failure type counts
- threshold pass/fail status
- threshold violations
- comparable run table
- baseline regression/improvement diffs

### Benefits

- Makes benchmark artifacts inspectable without reading raw JSON.
- Keeps benchmark comparison local-file friendly for AI agents and offline workflows.
- Starts the UI path toward regression review across simulation sweeps.
- Treats the first benchmark run as a baseline, which matches common CI and experiment workflows.

### Tradeoffs

- The dashboard currently loads benchmark files from the browser file picker rather than the FastAPI server.
- Plotly is still bundled eagerly, so the app bundle remains large.
- Metric normalization is not implemented yet; grouped bars are useful but not a final analytical view.
- Baseline diff uses a simple 5% band; future work should allow metric-specific regression budgets.

### Decision

Adopted for MVP. It turns `navigation-analyzer benchmark` output into a visual workflow while avoiding new backend endpoints.

### Validation

```text
scripts/run_sample_demo.sh outputs/demo_sample: passed
npm run build: passed
npm run check:visualization: loads outputs/demo_sample/benchmark.json and verifies desktop/mobile canvas
```

## 2026-05-13: Autoware LaneletRoute metadata extraction

### Tried

Parse `autoware_planning_msgs/msg/LaneletRoute` from `/planning/mission_planning/route` during ROS2 bag conversion and store a compact route summary in `NavigationRun.metadata`.

### Benefits

- Makes Autoware route context visible in JSON, Markdown, and the web UI.
- Captures lanelet primitive IDs without changing the canonical sample schema.
- Provides the next foundation for route-aware planner divergence and lanelet-relative final errors.

### Tradeoffs

- This is metadata only; it does not yet compute lanelet-relative cross-track error.
- Primitive IDs are capped in JSON previews to keep artifacts compact.
- The route reader is structure-based and intentionally avoids depending on Autoware Python types outside the ROS extraction boundary.

### Decision

Adopted. Route context belongs in metadata first; route-aware metrics can build on it once the semantics are stable.

### Validation

```text
autoware_planning_success_001:
  route_topic = /planning/mission_planning/route
  segment_count = 2
  primitive_count = 2
  unique_primitive_count = 2
  preferred_ids = [9803, 127]
  route_start = x=3810.300 y=73819.500 yaw=0.482
  route_goal = x=3850.000 y=73840.000 yaw=0.482
```

## 2026-05-13: Route-aware planner divergence evidence

### Tried

Enrich `planner_divergence` findings with Autoware route metadata when a `LaneletRoute` was extracted from the bag.

### Benefits

- Keeps the rule simple while making the output more useful for Autoware debugging.
- Ties divergence evidence to the mission route topic, preferred lanelet IDs, segment counts, and route goal distance.
- Gives AI agents enough context to distinguish route/planner mismatch from generic controller tracking failure.

### Tradeoffs

- This still compares pose samples to the extracted trajectory polyline; it does not compute true lanelet corridor distance.
- Route IDs are metadata evidence, not a geometric route model.

### Decision

Adopted. Route-aware evidence is a low-risk bridge toward lanelet-relative metrics without adding a hard Autoware map dependency to the analysis core.

### Validation

```text
Unit coverage:
  planner_divergence includes route_topic, route segment count, preferred lanelet IDs, and route_goal_distance_m.
```

## 2026-05-13: Autoware route fallback goal and straight-line progress metrics

### Tried

Use `LaneletRoute.goal_pose` as a fallback canonical goal when no explicit goal topic is extracted. Add route start-to-goal projection metrics:

- `route_progress_ratio`
- `route_straight_line_lateral_error`
- `route_straight_line_remaining_distance`

### Benefits

- Autoware bags remain evaluable even when only mission route messages are recorded.
- The metric names are explicit that this is a straight-line route approximation, not lanelet centerline distance.
- The values are cheap to compute and work in CI without Autoware map dependencies.

### Tradeoffs

- Curved routes and lane changes are not represented geometrically.
- This should not replace future lanelet2 map-aware corridor metrics.

### Decision

Adopted as an MVP bridge. It improves robustness for recorded tutorial bags while keeping the analysis core dependency-light.

### Validation

```text
Unit coverage:
  route goal summary converts to Pose2D.
  final pose at (5, 1) on a (0, 0) -> (10, 0) route gives progress=0.5, lateral=1.0, remaining=5.0.
```

## 2026-05-13: Lanelet2 OSM centerline metrics

### Tried

Parse `lanelet2_map.osm` directly, find preferred route lanelet relation IDs, construct centerlines from left/right boundaries, and compute route-relative metrics without importing Autoware or lanelet2 Python bindings.

### Benefits

- Adds map-aware evaluation while keeping the CLI usable in lightweight CI.
- Makes Autoware tutorial bags easier to evaluate because preferred lanelet IDs from `LaneletRoute` now connect to geometry.
- Avoids a hard runtime dependency on Autoware map libraries.

### Tradeoffs

- The parser handles lanelet centerlines only; it does not yet evaluate drivable corridor polygons or regulatory elements.
- Lat/lon conversion uses a local UTM/MGRS-style 100 km tile coordinate approximation, matching the sample map workflow but not yet a general geodesy layer.
- If no `lanelet2_map` is configured or mounted, lanelet metrics return `null` rather than failing the analysis.

### Decision

Adopted for MVP. Centerline distance is the first useful map-aware navigation metric and gives a concrete foundation for future corridor and regulatory-element checks.

### Validation

```text
Unit coverage:
  synthetic lanelet2 OSM relation -> centerline.
  route_lanelet_centerline_distance, mean/max distance, progress, remaining distance, and matched count.
```
