#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: scripts/analyze_autoware_bag_docker.sh <bag-or-navigation-json> [output-dir]" >&2
  exit 2
fi

INPUT="$1"
OUT="${2:-outputs/$(basename "${INPUT}")}"
AUTOWARE_IMAGE="${NAV_ANALYZER_AUTOWARE_IMAGE:-ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0}"
ANALYZER_IMAGE="${NAV_ANALYZER_AUTOWARE_ANALYZER_IMAGE:-navigation-analyzer-autoware:jazzy-1.8.0}"
MAP_DIR="${NAV_ANALYZER_AUTOWARE_MAP_DIR:-$HOME/autoware_data/maps/sample-map-planning}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
INPUT_ABS="$(realpath "${INPUT}")"
mkdir -p "${OUT}"
OUT_ABS="$(realpath "${OUT}")"

if ! docker image inspect "${ANALYZER_IMAGE}" >/dev/null 2>&1 || [[ "${NAV_ANALYZER_DOCKER_BUILD:-0}" == "1" ]]; then
  docker build \
    --build-arg "AUTOWARE_IMAGE=${AUTOWARE_IMAGE}" \
    -t "${ANALYZER_IMAGE}" \
    -f "${REPO_ROOT}/docker/autoware-analyzer/Dockerfile" \
    "${REPO_ROOT}"
fi

DOCKER_ARGS=(
  --rm
  --entrypoint bash
  -v "${REPO_ROOT}:/work:ro"
  -v "${INPUT_ABS}:/input:ro"
  -v "${OUT_ABS}:/output"
  -w /work
)

if [[ -d "${MAP_DIR}" ]]; then
  DOCKER_ARGS+=(-v "${MAP_DIR}:/home/aw/autoware_data/maps/sample-map-planning:ro")
fi

docker run "${DOCKER_ARGS[@]}" "${ANALYZER_IMAGE}" -lc '
set -euo pipefail
set +u
source /opt/ros/jazzy/setup.bash
source /opt/autoware/setup.bash
set -u
export PYTHONPATH=/work/backend:${PYTHONPATH:-}

python3 -m navigation_analyzer.cli.main convert \
  --bag /input \
  --config /work/config/autoware.yaml \
  --out /output/navigation_run.json

python3 -m navigation_analyzer.cli.main analyze \
  --bag /output/navigation_run.json \
  --config /work/config/autoware.yaml \
  --out /output

python3 -m navigation_analyzer.cli.main benchmark \
  --bag /output/navigation_run.json \
  --config /work/config/autoware.yaml \
  --thresholds /work/config/benchmark_autoware.yaml \
  --report /output/benchmark.md \
  --out /output/benchmark.json
'

echo "Autoware analysis written to ${OUT_ABS}"
