#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-bags/autoware_fixture_success_001}"
ANALYZER_IMAGE="${NAV_ANALYZER_AUTOWARE_ANALYZER_IMAGE:-navigation-analyzer-autoware:jazzy-1.8.0}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OUT_ABS="$(realpath -m "${OUT}")"
OUT_PARENT="$(dirname "${OUT_ABS}")"
OUT_NAME="$(basename "${OUT_ABS}")"

if [[ -e "${OUT_ABS}" ]]; then
  docker run --rm \
    --entrypoint rm \
    -v "${OUT_PARENT}:/cleanup" \
    "${ANALYZER_IMAGE}" \
    -rf "/cleanup/${OUT_NAME}"
fi
mkdir -p "$(dirname "${OUT}")"

docker run --rm \
  --entrypoint bash \
  -v "${REPO_ROOT}:/work" \
  -w /work \
  -e HOST_UID="$(id -u)" \
  -e HOST_GID="$(id -g)" \
  "${ANALYZER_IMAGE}" \
  -lc "
set -euo pipefail
set +u
source /opt/ros/jazzy/setup.bash
source /opt/autoware/setup.bash
set -u
python3 - \"${OUT}\" <<'PY'
import math
import sys
from pathlib import Path

import rosbag2_py
from autoware_control_msgs.msg import Control
from autoware_planning_msgs.msg import Trajectory, TrajectoryPoint
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.serialization import serialize_message
from rosbag2_py import TopicMetadata

out = Path(sys.argv[1])
writer = rosbag2_py.SequentialWriter()
writer.open(
    rosbag2_py.StorageOptions(uri=str(out), storage_id='mcap'),
    rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'),
)

for topic_id, (name, typ) in enumerate([
    ('/planning/mission_planning/goal', 'geometry_msgs/msg/PoseStamped'),
    ('/localization/kinematic_state', 'nav_msgs/msg/Odometry'),
    ('/control/command/control_cmd', 'autoware_control_msgs/msg/Control'),
    ('/planning/scenario_planning/trajectory', 'autoware_planning_msgs/msg/Trajectory'),
], start=1):
    writer.create_topic(TopicMetadata(id=topic_id, name=name, type=typ, serialization_format='cdr'))


def timestamp_ns(t: float) -> int:
    sec = int(t)
    return sec * 1_000_000_000 + int((t - sec) * 1_000_000_000)


def set_header(msg, t: float) -> None:
    sec = int(t)
    nanosec = int((t - sec) * 1_000_000_000)
    if hasattr(msg, 'header'):
        msg.header.stamp.sec = sec
        msg.header.stamp.nanosec = nanosec
        msg.header.frame_id = 'map'
    if hasattr(msg, 'stamp'):
        msg.stamp.sec = sec
        msg.stamp.nanosec = nanosec


def set_yaw(pose, yaw: float) -> None:
    pose.orientation.z = math.sin(yaw / 2.0)
    pose.orientation.w = math.cos(yaw / 2.0)


goal = PoseStamped()
set_header(goal, 0.0)
goal.pose.position.x = 3.0
goal.pose.position.y = 0.0
set_yaw(goal.pose, 0.0)
writer.write('/planning/mission_planning/goal', serialize_message(goal), timestamp_ns(0.0))

trajectory = Trajectory()
set_header(trajectory, 0.05)
for x in [0.0, 1.0, 2.0, 3.0]:
    point = TrajectoryPoint()
    point.pose.position.x = x
    point.pose.position.y = 0.0
    set_yaw(point.pose, 0.0)
    point.longitudinal_velocity_mps = 0.5
    trajectory.points.append(point)
writer.write('/planning/scenario_planning/trajectory', serialize_message(trajectory), timestamp_ns(0.05))

positions = [0.0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.0, 3.0, 3.0]
for index, x in enumerate(positions):
    t = 0.1 + index
    odom = Odometry()
    set_header(odom, t)
    odom.child_frame_id = 'base_link'
    odom.pose.pose.position.x = x
    odom.pose.pose.position.y = 0.0
    set_yaw(odom.pose.pose, 0.0)
    writer.write('/localization/kinematic_state', serialize_message(odom), timestamp_ns(t))

    control = Control()
    set_header(control, t)
    control.longitudinal.velocity = 0.0 if index >= 5 else 0.5
    control.lateral.steering_tire_angle = 0.0
    writer.write('/control/command/control_cmd', serialize_message(control), timestamp_ns(t) + 1)
PY
ros2 bag info \"${OUT}\"
chown -R \"\${HOST_UID}:\${HOST_GID}\" \"${OUT}\"
"
