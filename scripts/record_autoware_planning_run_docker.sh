#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-bags/autoware_planning_success_001}"
AUTOWARE_IMAGE="${NAV_ANALYZER_AUTOWARE_IMAGE:-ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0}"
ANALYZER_IMAGE="${NAV_ANALYZER_AUTOWARE_ANALYZER_IMAGE:-navigation-analyzer-autoware:jazzy-1.8.0}"
MAP_DIR="${NAV_ANALYZER_AUTOWARE_MAP_DIR:-$HOME/autoware_data/maps/sample-map-planning}"
ML_MODELS_DIR="${NAV_ANALYZER_AUTOWARE_ML_MODELS_DIR:-$HOME/autoware_data/ml_models}"
RVIZ="${NAV_ANALYZER_AUTOWARE_RVIZ:-false}"
USE_SIM_TIME="${NAV_ANALYZER_AUTOWARE_USE_SIM_TIME:-false}"
INITIAL="${NAV_ANALYZER_AUTOWARE_INITIAL:-3810.3 73819.5 19.4 0.482}"
GOAL="${NAV_ANALYZER_AUTOWARE_GOAL:-3850.0 73840.0 19.4 0.482}"
LAUNCH_WAIT="${NAV_ANALYZER_AUTOWARE_LAUNCH_WAIT:-30}"
DRIVE_WAIT="${NAV_ANALYZER_AUTOWARE_DRIVE_WAIT:-25}"
RECORD_WARMUP="${NAV_ANALYZER_RECORD_WARMUP:-3}"
RECORD_TAIL="${NAV_ANALYZER_RECORD_TAIL:-5}"
RECORD_STORAGE="${NAV_ANALYZER_RECORD_STORAGE:-mcap}"
OVERWRITE="${NAV_ANALYZER_RECORD_OVERWRITE:-0}"
CONTAINER_NAME="${NAV_ANALYZER_AUTOWARE_CONTAINER:-navan-autoware-record-$(date +%s)}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OUT_ABS="$(realpath -m "${OUT}")"

case "${OUT_ABS}" in
  "${REPO_ROOT}"/*) BAG_IN_CONTAINER="/work/${OUT_ABS#"${REPO_ROOT}/"}" ;;
  *)
    echo "Output bag must be inside the repository: ${REPO_ROOT}" >&2
    exit 2
    ;;
esac

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

if [[ -e "${OUT_ABS}" ]]; then
  if [[ "${OVERWRITE}" == "1" ]]; then
    rm -rf "${OUT_ABS}"
  else
    echo "Output already exists: ${OUT_ABS}" >&2
    echo "Set NAV_ANALYZER_RECORD_OVERWRITE=1 to replace it." >&2
    exit 2
  fi
fi

mkdir -p "$(dirname "${OUT_ABS}")" "${ML_MODELS_DIR}"

if ! docker image inspect "${ANALYZER_IMAGE}" >/dev/null 2>&1; then
  docker build \
    --build-arg "AUTOWARE_IMAGE=${AUTOWARE_IMAGE}" \
    -t "${ANALYZER_IMAGE}" \
    -f "${REPO_ROOT}/docker/autoware-analyzer/Dockerfile" \
    "${REPO_ROOT}"
fi

DOCKER_ARGS=(
  --rm
  --name "${CONTAINER_NAME}"
  --ipc host
  --privileged
  --entrypoint bash
  -e CYCLONEDDS_URI=file:///tmp/cyclonedds_docker_eth0.xml
  -e DISPLAY="${DISPLAY:-}"
  -e QT_X11_NO_MITSHM=1
  -e NAV_ANALYZER_RECORD_BAG="${BAG_IN_CONTAINER}"
  -e NAV_ANALYZER_RECORD_STORAGE="${RECORD_STORAGE}"
  -e NAV_ANALYZER_RECORD_WARMUP="${RECORD_WARMUP}"
  -e NAV_ANALYZER_RECORD_TAIL="${RECORD_TAIL}"
  -e NAV_ANALYZER_AUTOWARE_RVIZ="${RVIZ}"
  -e NAV_ANALYZER_AUTOWARE_USE_SIM_TIME="${USE_SIM_TIME}"
  -e NAV_ANALYZER_AUTOWARE_INITIAL="${INITIAL}"
  -e NAV_ANALYZER_AUTOWARE_GOAL="${GOAL}"
  -e NAV_ANALYZER_AUTOWARE_LAUNCH_WAIT="${LAUNCH_WAIT}"
  -e NAV_ANALYZER_AUTOWARE_DRIVE_WAIT="${DRIVE_WAIT}"
  -e NAV_ANALYZER_HOST_UID="$(id -u)"
  -e NAV_ANALYZER_HOST_GID="$(id -g)"
  -v "${REPO_ROOT}/config/cyclonedds_docker_eth0.xml:/tmp/cyclonedds_docker_eth0.xml:ro"
  -v "${MAP_DIR}:/home/aw/autoware_data/maps/sample-map-planning:ro"
  -v "${ML_MODELS_DIR}:/home/aw/autoware_data/ml_models:ro"
  -v "${REPO_ROOT}:/work"
  -w /work
)

if [[ "${RVIZ}" == "true" ]]; then
  DOCKER_ARGS+=(-v /tmp/.X11-unix:/tmp/.X11-unix:rw)
fi

docker run "${DOCKER_ARGS[@]}" "${ANALYZER_IMAGE}" -lc '
set -euo pipefail
set +u
source /opt/ros/jazzy/setup.bash
source /opt/autoware/setup.bash
set -u
export CYCLONEDDS_URI=file:///tmp/cyclonedds_docker_eth0.xml

launch_cmd=(
  ros2 launch autoware_launch planning_simulator.launch.xml
  map_path:=/home/aw/autoware_data/maps/sample-map-planning
  vehicle_model:=sample_vehicle
  sensor_model:=sample_sensor_kit
  rviz:="${NAV_ANALYZER_AUTOWARE_RVIZ}"
  use_sim_time:="${NAV_ANALYZER_AUTOWARE_USE_SIM_TIME}"
)

topics=(
  /tf
  /tf_static
  /initialpose
  /initialpose3d
  /localization/kinematic_state
  /planning/mission_planning/goal
  /planning/mission_planning/echo_back_goal_pose
  /planning/mission_planning/route
  /planning/scenario_planning/trajectory
  /planning/scenario_planning/lane_driving/trajectory
  /control/command/control_cmd
  /control/trajectory_follower/control_cmd
  /vehicle/status/velocity_status
  /api/routing/state
  /api/operation_mode/state
  /autoware/state
  /sensing/lidar/top/pointcloud
  /sensing/lidar/concatenated/pointcloud
  /planning/scenario_planning/parking/costmap
)

cleanup() {
  set +e
  if [[ -n "${record_pid:-}" ]] && kill -0 "${record_pid}" 2>/dev/null; then
    kill -INT "${record_pid}" 2>/dev/null || true
    for _ in {1..15}; do
      kill -0 "${record_pid}" 2>/dev/null || break
      sleep 1
    done
    kill -TERM "${record_pid}" 2>/dev/null || true
    for _ in {1..5}; do
      kill -0 "${record_pid}" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "${record_pid}" 2>/dev/null || true
    wait "${record_pid}" 2>/dev/null || true
  fi
  if [[ -n "${launch_pid:-}" ]] && kill -0 "${launch_pid}" 2>/dev/null; then
    kill -INT "${launch_pid}" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "${launch_pid}" 2>/dev/null || break
      sleep 1
    done
    kill -TERM "${launch_pid}" 2>/dev/null || true
    sleep 1
    kill -KILL "${launch_pid}" 2>/dev/null || true
  fi
  if [[ -e "${NAV_ANALYZER_RECORD_BAG}" ]]; then
    chown -R "${NAV_ANALYZER_HOST_UID}:${NAV_ANALYZER_HOST_GID}" "${NAV_ANALYZER_RECORD_BAG}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

"${launch_cmd[@]}" &
launch_pid=$!
echo "Waiting ${NAV_ANALYZER_AUTOWARE_LAUNCH_WAIT}s for Autoware planning simulator..."
sleep "${NAV_ANALYZER_AUTOWARE_LAUNCH_WAIT}"

mkdir -p "$(dirname "${NAV_ANALYZER_RECORD_BAG}")"
record_args=(-o "${NAV_ANALYZER_RECORD_BAG}")
if [[ -n "${NAV_ANALYZER_RECORD_STORAGE}" ]]; then
  record_args=(-s "${NAV_ANALYZER_RECORD_STORAGE}" "${record_args[@]}")
fi

ros2 bag record "${record_args[@]}" "${topics[@]}" &
record_pid=$!
sleep "${NAV_ANALYZER_RECORD_WARMUP}"

read -r -a initial_args <<< "${NAV_ANALYZER_AUTOWARE_INITIAL}"
read -r -a goal_args <<< "${NAV_ANALYZER_AUTOWARE_GOAL}"
python3 /work/scripts/autoware_drive_goal.py \
  --initial "${initial_args[@]}" \
  --goal "${goal_args[@]}" \
  --wait-after-engage "${NAV_ANALYZER_AUTOWARE_DRIVE_WAIT}"

sleep "${NAV_ANALYZER_RECORD_TAIL}"
kill -INT "${record_pid}" 2>/dev/null || true
for _ in {1..15}; do
  if ! kill -0 "${record_pid}" 2>/dev/null; then
    break
  fi
  sleep 1
done
if kill -0 "${record_pid}" 2>/dev/null; then
  kill -TERM "${record_pid}" 2>/dev/null || true
  for _ in {1..5}; do
    if ! kill -0 "${record_pid}" 2>/dev/null; then
      break
    fi
    sleep 1
  done
fi
if kill -0 "${record_pid}" 2>/dev/null; then
  kill -KILL "${record_pid}" 2>/dev/null || true
fi
record_rc=0
wait "${record_pid}" || record_rc=$?
if [[ ${record_rc} -ne 0 && ${record_rc} -ne 130 && ${record_rc} -ne 137 && ${record_rc} -ne 143 ]]; then
  exit "${record_rc}"
fi

echo "Recorded Autoware planning bag: ${NAV_ANALYZER_RECORD_BAG}"
'

echo "Autoware planning run bag written to ${OUT_ABS}"
