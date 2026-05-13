#!/usr/bin/env bash
set -euo pipefail

X="${1:?Usage: scripts/send_nav2_goal.sh <x> <y> [yaw_rad]}"
Y="${2:?Usage: scripts/send_nav2_goal.sh <x> <y> [yaw_rad]}"
YAW="${3:-0.0}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 command not found. Source your ROS2 environment first." >&2
  exit 1
fi

read -r QZ QW < <(python3 - <<PY
import math
yaw = float("${YAW}")
print(math.sin(yaw / 2.0), math.cos(yaw / 2.0))
PY
)

GOAL="{header: {frame_id: map}, pose: {position: {x: ${X}, y: ${Y}, z: 0.0}, orientation: {z: ${QZ}, w: ${QW}}}}"

ros2 topic pub --times 5 --rate 2 /goal_pose geometry_msgs/msg/PoseStamped "${GOAL}" >/tmp/navigation_analyzer_goal_pose.log 2>&1 &

ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: ${GOAL}}"
