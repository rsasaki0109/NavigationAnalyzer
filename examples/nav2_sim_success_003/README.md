# Nav2 Simulation Success Fixture

This fixture is a compact canonical JSON export from a ROS2 Jazzy Nav2 TurtleBot3 simulation bag.

Source bag:

```text
bags/nav2_sim_success_003
```

Raw bag summary:

```text
Duration: 43.99s
Messages: 4161
Topics: /tf, /odom, /scan, /cmd_vel, /cmd_vel_smoothed, /plan, /goal_pose, costmaps
Action result: NavigateToPose reached goal tolerance during the recording
```

Compaction:

- Original canonical samples: 628
- Compact fixture samples: 103
- Costmap omitted to keep the repository small
- Preserved windows around goal reach, minimum obstacle distance, and narrow-passage warning

Expected analysis:

```text
success_rate = 1.0
time_to_goal ~= 3.744s
goal_distance ~= 0.181m
final_lateral_error ~= -0.058m
final_longitudinal_error ~= -0.171m
final_yaw_error ~= 0.191rad
final_stopped_duration ~= 17.388s
failure_types = ["narrow_passage_failure"]
```
