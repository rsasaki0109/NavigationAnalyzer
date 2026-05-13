#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-outputs/demo_sample}"
PYTHON="${PYTHON:-python3}"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
else
  export PYTHONPATH="$(pwd)/backend"
fi

mkdir -p "${OUT}"

"${PYTHON}" -m navigation_analyzer.cli.main analyze \
  --bag examples/sample_bag/sample_navigation.json \
  --config config/default.yaml \
  --out "${OUT}/sample_failure"

"${PYTHON}" -m navigation_analyzer.cli.main analyze \
  --bag examples/nav2_sim_success_003/navigation_run.json \
  --config config/default.yaml \
  --out "${OUT}/nav2_success"

"${PYTHON}" -m navigation_analyzer.cli.main benchmark \
  --bag examples/nav2_sim_success_003/navigation_run.json \
  --bag examples/sample_bag/sample_navigation.json \
  --config config/default.yaml \
  --report "${OUT}/benchmark.md" \
  --out "${OUT}/benchmark.json"

cat <<EOF
Demo artifacts written to ${OUT}

Open these first:
  ${OUT}/sample_failure/report.md
  ${OUT}/nav2_success/report.md
  ${OUT}/benchmark.md

Serve the sample failure in the web UI:
  PYTHONPATH=backend python3 -m navigation_analyzer.cli.main serve --analysis ${OUT}/sample_failure/analysis.json --port 8000
  cd frontend && npm install && npm run dev
EOF
