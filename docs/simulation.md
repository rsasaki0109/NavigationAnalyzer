# Simulation Fixtures

Use simulation to create real ROS2 bags for NavigationAnalyzer development. The recommended first target is TurtleBot3 + Nav2 because it is small, reproducible, and exposes standard navigation topics.

## Recommended Setup

Use one ROS2 distro consistently. Humble and Jazzy are both reasonable choices. Replace `humble` below with your distro if needed.

```bash
source /opt/ros/humble/setup.bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-gazebo
```

Set the TurtleBot3 model:

```bash
export TURTLEBOT3_MODEL=waffle
```

## Start Simulation

Terminal 1:

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

Terminal 2:

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle
ros2 launch nav2_bringup bringup_launch.py \
  use_sim_time:=True \
  map:=$HOME/map.yaml
```

If you do not have a map yet, create one with SLAM first or use a known TurtleBot3/Nav2 map from your local setup.

## Record a Bag

Terminal 3, from this repository:

```bash
source /opt/ros/humble/setup.bash
scripts/record_nav2_sim_bag.sh bags/nav2_sim_001
```

Then send a goal from RViz or CLI. Stop recording after the robot succeeds or fails.

For CLI-driven goals, use:

```bash
scripts/send_nav2_goal.sh 1.5 0.5 0.0
```

The helper publishes `/goal_pose` several times so the bag reliably captures the goal, then sends the Nav2 `NavigateToPose` action. Capturing `/goal_pose` matters because NavigationAnalyzer uses it as the run goal for success, goal distance, and time-to-goal metrics.

For a fixed-duration recording:

```bash
NAV_ANALYZER_RECORD_DURATION=90s scripts/record_nav2_sim_bag.sh bags/nav2_sim_001
```

## Analyze the Bag

```bash
source /opt/ros/humble/setup.bash
scripts/analyze_sim_bag.sh bags/nav2_sim_001 outputs/nav2_sim_001
```

This writes:

- `outputs/nav2_sim_001/navigation_run.json`
- `outputs/nav2_sim_001/analysis.json`
- `outputs/nav2_sim_001/report.md`

## Validate Topics Before Recording

```bash
ros2 topic list
ros2 topic hz /odom
ros2 topic hz /cmd_vel
ros2 topic hz /scan
```

NavigationAnalyzer defaults are in `config/default.yaml` under `rosbag_topics`. If your stack uses different names, update the config rather than changing code.

For Nav2, keep `/tf` in the bag. NavigationAnalyzer composes `map -> odom` and `odom -> base_footprint` when available so trajectory and goal distance are evaluated in the map frame. Raw `/odom` alone is not enough when the goal is in `map`.

## Useful Failure Scenarios

Create one bag per scenario. Keep each recording small, usually 30 to 120 seconds.

| Scenario | How to trigger |
| --- | --- |
| clean_success | Send an easy goal in open space |
| narrow_passage | Use a doorway or corridor near robot footprint limits |
| oscillation | Send a goal near an obstacle or tight corner |
| deadlock | Block the path with a simulated obstacle |
| dynamic_obstacle_freeze | Move an obstacle across the local planner path |
| planner_divergence | Change the scene after the global plan is computed |

## Fixture Naming

Use stable names so benchmark outputs are easy to compare:

```text
bags/
  nav2_clean_success_001/
  nav2_narrow_passage_001/
  nav2_oscillation_001/
  nav2_deadlock_001/
```

Generated bags are ignored by git. Keep small canonical JSON exports in `examples/` only when they are useful as lightweight regression fixtures.

## Current Limitation

The ROS2 bag adapter extracts common message types, but recovery semantics are still shallow. For high-quality Nav2 failure attribution, later work should parse behavior tree status and action feedback topics.
