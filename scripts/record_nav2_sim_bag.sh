#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-bags/nav2_sim_$(date +%Y%m%d_%H%M%S)}"
DURATION="${NAV_ANALYZER_RECORD_DURATION:-0}"

TOPICS=(
  /odom
  /amcl_pose
  /cmd_vel
  /cmd_vel_smoothed
  /scan
  /tf
  /tf_static
  /plan
  /global_plan
  /local_plan
  /global_costmap/costmap
  /local_costmap/costmap
  /goal_pose
  /behavior_server/transition_event
  /recoveries
  /recovery_status
)

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 command not found. Source your ROS2 environment first." >&2
  echo "Example: source /opt/ros/humble/setup.bash" >&2
  exit 1
fi

echo "Recording Nav2 simulation bag to: ${OUT}"
echo "Missing topics are usually harmless if your stack uses different names."

if [[ "${DURATION}" == "0" ]]; then
  ros2 bag record -o "${OUT}" "${TOPICS[@]}"
else
  timeout --signal=INT --kill-after=5s "${DURATION}" ros2 bag record -o "${OUT}" "${TOPICS[@]}"
fi
