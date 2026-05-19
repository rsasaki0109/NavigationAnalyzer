#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
OUT_ROOT="${1:-outputs/zoo}"
ZOO_DIR="examples/zoo"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
else
  export PYTHONPATH="$(pwd)/backend"
fi

# Regenerate fixtures so the source of truth is the generator script.
"${PYTHON}" "${ZOO_DIR}/generate.py"

mkdir -p "${OUT_ROOT}"

for fixture in "${ZOO_DIR}"/*/navigation_run.json; do
  name="$(basename "$(dirname "${fixture}")")"
  out_dir="${OUT_ROOT}/${name}"
  "${PYTHON}" -m navigation_analyzer.cli.main analyze \
    --bag "${fixture}" \
    --config config/default.yaml \
    --out "${out_dir}"
  cp "${out_dir}/diagnosis.md" "${ZOO_DIR}/${name}/diagnosis.md"
done

cat <<EOF
Failure zoo regenerated.

Snapshots committed beside each fixture:
  examples/zoo/<name>/navigation_run.json
  examples/zoo/<name>/diagnosis.md

Full analysis artifacts (analysis.json, diagnosis_pack.json, report.md):
  ${OUT_ROOT}/<name>/
EOF
