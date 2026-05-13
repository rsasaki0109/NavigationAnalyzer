#!/usr/bin/env bash
set -euo pipefail

IMAGE="${NAV_ANALYZER_AUTOWARE_IMAGE:-ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0}"
MAP_DIR="${NAV_ANALYZER_AUTOWARE_MAP_DIR:-$HOME/autoware_data/maps/sample-map-planning}"
ML_MODELS_DIR="${NAV_ANALYZER_AUTOWARE_ML_MODELS_DIR:-$HOME/autoware_data/ml_models}"
RVIZ="${NAV_ANALYZER_AUTOWARE_RVIZ:-false}"
USE_SIM_TIME="${NAV_ANALYZER_AUTOWARE_USE_SIM_TIME:-false}"
RECORD_BAG="${NAV_ANALYZER_RECORD_BAG:-}"
RECORD_DURATION="${NAV_ANALYZER_RECORD_DURATION:-0}"

if [[ ! -d "${MAP_DIR}" ]]; then
  cat >&2 <<EOF
Autoware sample map not found: ${MAP_DIR}

Download it with:
  mkdir -p ~/autoware_data/maps
  gdown -O ~/autoware_data/maps/ 'https://docs.google.com/uc?export=download&id=1499_nsbUbIeturZaDj7jhUownh5fvXHd'
  unzip -d ~/autoware_data/maps ~/autoware_data/maps/sample-map-planning.zip
EOF
  exit 1
fi

mkdir -p "${ML_MODELS_DIR}" bags outputs/autoware

DOCKER_ARGS=(
  --rm
  --ipc host
  --privileged
  --entrypoint bash
  -e CYCLONEDDS_URI=file:///tmp/cyclonedds_docker_eth0.xml
  -e DISPLAY="${DISPLAY:-}"
  -e QT_X11_NO_MITSHM=1
  -v "$PWD/config/cyclonedds_docker_eth0.xml:/tmp/cyclonedds_docker_eth0.xml:ro"
  -v "${MAP_DIR}:/home/aw/autoware_data/maps/sample-map-planning:ro"
  -v "${ML_MODELS_DIR}:/home/aw/autoware_data/ml_models:ro"
  -v "$PWD:/work"
  -w /work
)

if [[ "${RVIZ}" == "true" ]]; then
  DOCKER_ARGS+=(-v /tmp/.X11-unix:/tmp/.X11-unix:rw)
fi

docker run "${DOCKER_ARGS[@]}" "${IMAGE}" -lc "
set -euo pipefail
set +u
source /opt/autoware/setup.bash
set -u
export CYCLONEDDS_URI=file:///tmp/cyclonedds_docker_eth0.xml

launch_cmd=(
  ros2 launch autoware_launch planning_simulator.launch.xml
  map_path:=/home/aw/autoware_data/maps/sample-map-planning
  vehicle_model:=sample_vehicle
  sensor_model:=sample_sensor_kit
  rviz:=${RVIZ}
  use_sim_time:=${USE_SIM_TIME}
)

topics=(
  /tf
  /tf_static
  /localization/kinematic_state
  /planning/mission_planning/goal
  /planning/mission_planning/echo_back_goal_pose
  /planning/scenario_planning/trajectory
  /planning/scenario_planning/lane_driving/trajectory
  /control/command/control_cmd
  /control/trajectory_follower/control_cmd
  /sensing/lidar/top/pointcloud
  /sensing/lidar/concatenated/pointcloud
  /planning/scenario_planning/parking/costmap
)

if [[ -z \"${RECORD_BAG}\" ]]; then
  exec \"\${launch_cmd[@]}\"
fi

\"\${launch_cmd[@]}\" &
launch_pid=\$!
trap 'kill -INT \${record_pid:-} \${launch_pid:-} 2>/dev/null || true' INT TERM EXIT
sleep 10
mkdir -p \"\$(dirname \"${RECORD_BAG}\")\"
if [[ \"${RECORD_DURATION}\" == \"0\" ]]; then
  ros2 bag record -o \"${RECORD_BAG}\" \"\${topics[@]}\" &
else
  timeout --signal=INT --kill-after=5s \"${RECORD_DURATION}\" ros2 bag record -o \"${RECORD_BAG}\" \"\${topics[@]}\" &
fi
record_pid=\$!
record_rc=0
wait \${record_pid} || record_rc=\$?
if [[ \${record_rc} -ne 0 && \${record_rc} -ne 124 ]]; then
  exit \${record_rc}
fi
kill -INT \${launch_pid} 2>/dev/null || true
for _ in {1..15}; do
  if ! kill -0 \${launch_pid} 2>/dev/null; then
    exit 0
  fi
  sleep 1
done
kill -TERM \${launch_pid} 2>/dev/null || true
sleep 2
kill -KILL \${launch_pid} 2>/dev/null || true
"
