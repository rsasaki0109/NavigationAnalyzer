#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-bags/autoware_$(date +%Y%m%d_%H%M%S)}"
DURATION="${NAV_ANALYZER_RECORD_DURATION:-0}"

TOPICS=(
  /tf
  /tf_static
  /localization/kinematic_state
  /localization/pose_twist_fusion_filter/pose_with_covariance
  /localization/pose_estimator/pose_with_covariance
  /planning/mission_planning/goal
  /planning/mission_planning/echo_back_goal_pose
  /planning/mission_planning/modified_goal
  /planning/scenario_planning/trajectory
  /planning/scenario_planning/lane_driving/trajectory
  /control/command/control_cmd
  /control/trajectory_follower/control_cmd
  /sensing/lidar/top/pointcloud
  /sensing/lidar/concatenated/pointcloud
  /points_raw
  /planning/scenario_planning/parking/costmap
)

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 command not found. Source your Autoware workspace first." >&2
  echo "Example: source ~/autoware/install/setup.bash" >&2
  exit 1
fi

echo "Recording Autoware bag to: ${OUT}"
echo "Missing topics are usually harmless across Autoware versions and launch profiles."

if [[ "${DURATION}" == "0" ]]; then
  ros2 bag record -o "${OUT}" "${TOPICS[@]}"
else
  timeout --signal=INT --kill-after=5s "${DURATION}" ros2 bag record -o "${OUT}" "${TOPICS[@]}"
fi
