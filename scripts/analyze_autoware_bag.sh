#!/usr/bin/env bash
set -euo pipefail

BAG="${1:?Usage: scripts/analyze_autoware_bag.sh <bag-dir> [output-dir]}"
OUT="${2:-outputs/$(basename "${BAG}")}"

export PYTHONPATH="${PYTHONPATH:-}:backend"

python3 -m navigation_analyzer.cli.main convert \
  --bag "${BAG}" \
  --config config/autoware.yaml \
  --out "${OUT}/navigation_run.json"

python3 -m navigation_analyzer.cli.main analyze \
  --bag "${OUT}/navigation_run.json" \
  --config config/autoware.yaml \
  --out "${OUT}"

python3 -m navigation_analyzer.cli.main benchmark \
  --bag "${OUT}/navigation_run.json" \
  --config config/autoware.yaml \
  --thresholds config/benchmark_autoware.yaml \
  --report "${OUT}/benchmark.md" \
  --out "${OUT}/benchmark.json"

echo "Autoware analysis written to ${OUT}"
