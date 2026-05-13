# Autoware Workflow

NavigationAnalyzer can analyze Autoware bags through the canonical `NavigationRun` schema. The current support is a beta topic profile: it maps common Autoware localization, control, trajectory, pointcloud, and mission-goal topics, then applies the same metric and benchmark system used by Nav2 fixtures.

## Docker Runtime Install

The current local baseline uses the official Autoware Docker runtime instead of a full source build:

```bash
docker pull ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0
git clone --branch 1.8.0 --depth 1 https://github.com/autowarefoundation/autoware.git ~/autoware
```

The sample planning map is expected at:

```bash
~/autoware_data/maps/sample-map-planning
```

If it is missing:

```bash
mkdir -p ~/autoware_data/maps
gdown -O ~/autoware_data/maps/ 'https://docs.google.com/uc?export=download&id=1499_nsbUbIeturZaDj7jhUownh5fvXHd'
unzip -d ~/autoware_data/maps ~/autoware_data/maps/sample-map-planning.zip
```

Run the planning simulator without RViz:

```bash
scripts/run_autoware_planning_simulator_docker.sh
```

Run with RViz:

```bash
xhost +local:docker
NAV_ANALYZER_AUTOWARE_RVIZ=true scripts/run_autoware_planning_simulator_docker.sh
```

Record a short bag from inside the same Autoware container:

```bash
NAV_ANALYZER_RECORD_BAG=bags/autoware_planning_001 \
NAV_ANALYZER_RECORD_DURATION=120s \
scripts/run_autoware_planning_simulator_docker.sh
```

Run, drive, record, and close a headless planning-simulator bag with default sample-map coordinates:

```bash
NAV_ANALYZER_RECORD_OVERWRITE=1 \
scripts/record_autoware_planning_run_docker.sh bags/autoware_planning_success_001
```

The default route is:

```text
initial: x=3810.3 y=73819.5 z=19.4 yaw=0.482
goal:    x=3850.0 y=73840.0 z=19.4 yaw=0.482
```

Override it with:

```bash
NAV_ANALYZER_AUTOWARE_INITIAL="3810.3 73819.5 19.4 0.482" \
NAV_ANALYZER_AUTOWARE_GOAL="3850.0 73840.0 19.4 0.482" \
scripts/record_autoware_planning_run_docker.sh bags/my_autoware_run
```

The Docker image's default CycloneDDS config pins `lo`. On this host that failed because loopback multicast is disabled, so the script mounts `config/cyclonedds_docker_eth0.xml` and uses Docker `eth0`.

## Analyze Autoware Bags in Docker

Host ROS 2 may not have Autoware message packages installed. Use the analyzer-in-container path when reading raw Autoware bags:

```bash
scripts/analyze_autoware_bag_docker.sh bags/autoware_planning_001 outputs/autoware_planning_001
```

Example validated headless run:

```text
bags/autoware_planning_success_001:
  success_rate = 1.0
  path_length = 44.708 m
  goal_distance = 0.026 m
  time_to_goal = 17.050 s
  route_lanelet_centerline_distance = 0.230 m
  route_lanelet_matched_count = 2
  failures = 0
  benchmark_autoware = passed
```

The analyzer also extracts Autoware `autoware_planning_msgs/msg/LaneletRoute` metadata from `/planning/mission_planning/route` when present. The route summary is stored under `run.metadata.route_summary` and rendered in the Markdown/Web reports:

```text
route_topic = /planning/mission_planning/route
segment_count = 2
primitive_count = 2
preferred_lanelet_ids = [9803, 127]
route_start = (3810.300, 73819.500, yaw=0.482)
route_goal = (3850.000, 73840.000, yaw=0.482)
```

When `~/autoware_data/maps/sample-map-planning/lanelet2_map.osm` is available, the Docker analyzer mounts it and enables lanelet centerline metrics from the preferred route lanelet IDs.

The first run builds a small derived image:

```text
navigation-analyzer-autoware:jazzy-1.8.0
```

It is based on the official Autoware runtime image and adds only the Python packages needed by NavigationAnalyzer's CLI. Force a rebuild after dependency changes:

```bash
NAV_ANALYZER_DOCKER_BUILD=1 scripts/analyze_autoware_bag_docker.sh bags/autoware_planning_001 outputs/autoware_planning_001
```

Generate a tiny Autoware-message fixture bag for adapter validation:

```bash
scripts/create_autoware_fixture_bag_docker.sh bags/autoware_fixture_success_001
scripts/analyze_autoware_bag_docker.sh bags/autoware_fixture_success_001 outputs/autoware_fixture_success_001
```

## Official Tutorial Routes

Autoware's official documentation gives three useful routes for creating data:

- Planning simulation launches `planning_simulator.launch.xml` with `map_path`, `vehicle_model`, and `sensor_model`.
- Rosbag replay simulation launches `logging_simulator.launch.xml` and plays the sample rosbag.
- Scenario simulation runs `scenario_test_runner.launch.py` with a scenario file and optional recording.

References:

- Planning simulation: https://autowarefoundation.github.io/autoware-documentation/main/demos/planning-sim/
- Rosbag replay simulation: https://autowarefoundation.github.io/autoware-documentation/main/demos/rosbag-replay-simulation/
- Scenario test simulation: https://autowarefoundation.github.io/autoware-documentation/main/demos/scenario-simulation/scenario-simulator/scenario-test-simulation/

## Planning Simulator

From an Autoware workspace:

```bash
source ~/autoware/install/setup.bash
ros2 launch autoware_launch planning_simulator.launch.xml \
  map_path:=$HOME/autoware_data/maps/sample-map-planning \
  vehicle_model:=sample_vehicle \
  sensor_model:=sample_sensor_kit
```

In another terminal:

```bash
source ~/autoware/install/setup.bash
NAV_ANALYZER_RECORD_DURATION=120s scripts/record_autoware_bag.sh bags/autoware_planning_001
```

Set an initial pose and goal in RViz, then let the vehicle reach or fail the goal.

Analyze:

```bash
scripts/analyze_autoware_bag.sh bags/autoware_planning_001 outputs/autoware_planning_001
```

## Rosbag Replay

The official replay tutorial downloads a sample map into `~/autoware_data/maps/sample-map-rosbag/` and a sample rosbag into `~/autoware_data/recordings/bags/sample-rosbag/`.

Launch:

```bash
source ~/autoware/install/setup.bash
ros2 launch autoware_launch logging_simulator.launch.xml \
  map_path:=$HOME/autoware_data/maps/sample-map-rosbag \
  vehicle_model:=sample_vehicle \
  sensor_model:=sample_sensor_kit
```

Play:

```bash
source ~/autoware/install/setup.bash
ros2 bag play ~/autoware_data/recordings/bags/sample-rosbag/ -r 0.2 -s sqlite3
```

If you want a smaller derived bag for NavigationAnalyzer, record selected topics while the replay runs:

```bash
NAV_ANALYZER_RECORD_DURATION=120s scripts/record_autoware_bag.sh bags/autoware_replay_001
scripts/analyze_autoware_bag.sh bags/autoware_replay_001 outputs/autoware_replay_001
```

## Scenario Simulator

If Scenario Simulator is installed, the official command shape is:

```bash
source install/setup.bash
ros2 launch scenario_test_runner scenario_test_runner.launch.py \
  architecture_type:=awf/universe/20250130 \
  record:=false \
  scenario:='$(find-pkg-share scenario_test_runner)/scenario/sample.yaml' \
  sensor_model:=sample_sensor_kit \
  vehicle_model:=sample_vehicle \
  use_custom_centerline:=true \
  rviz_config:=$(ros2 pkg prefix autoware_launch)/share/autoware_launch/rviz/scenario_simulator.rviz
```

Run `scripts/record_autoware_bag.sh` in parallel, or set the simulator's native recording options and analyze the resulting bag with `scripts/analyze_autoware_bag.sh`.

## Current Autoware Coverage

The beta reader currently supports:

- `geometry_msgs/PoseStamped` and `PoseWithCovarianceStamped` goals.
- `nav_msgs/Odometry` and pose-with-covariance localization.
- `autoware_control_msgs/msg/Control` as velocity and steering proxy.
- `autoware_planning_msgs/msg/Trajectory` points as planned path.
- `autoware_planning_msgs/msg/LaneletRoute` as route metadata and preferred lanelet IDs.
- lanelet2 OSM left/right boundaries as preferred-route centerline geometry.
- PointCloud2 minimum obstacle distance when `sensor_msgs_py` is available.

Known gaps:

- Lanelet corridor polygon distance and regulatory element semantics are not evaluated yet.
- Goal-frame lateral and longitudinal errors are still separate from lanelet centerline metrics.
- Steering is stored in `cmd_w` as a temporary proxy until vehicle-control fields are added to the canonical schema.
