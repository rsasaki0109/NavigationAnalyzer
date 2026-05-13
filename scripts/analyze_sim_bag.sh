#!/usr/bin/env bash
set -euo pipefail

BAG="${1:?Usage: scripts/analyze_sim_bag.sh <bag-dir> [output-dir]}"
OUT="${2:-outputs/$(basename "${BAG}")}"

export PYTHONPATH="${PYTHONPATH:-}:backend"

python3 -m navigation_analyzer.cli.main convert \
  --bag "${BAG}" \
  --config config/default.yaml \
  --out "${OUT}/navigation_run.json"

python3 -m navigation_analyzer.cli.main analyze \
  --bag "${OUT}/navigation_run.json" \
  --config config/default.yaml \
  --out "${OUT}"

echo "Analysis written to ${OUT}"
