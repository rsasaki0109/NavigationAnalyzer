# GitHub Action: NavigationAnalyzer

`action.yml` at the repository root exposes NavigationAnalyzer as a composite
GitHub Action. Drop it into any workflow to gate navigation regressions on
PRs and surface a Markdown diagnosis directly in the PR Checks page.

## Quick start

```yaml
jobs:
  navigation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rsasaki0109/NavigationAnalyzer@v0
        with:
          bag: artifacts/nav_smoke.json
          fail-on-regression: true
```

What the action does:

1. Installs NavigationAnalyzer (Python 3.12 by default).
2. Runs `navigation-analyzer analyze` on the bag.
3. Appends the generated `diagnosis.md` to `$GITHUB_STEP_SUMMARY` so the
   PASS/FAIL verdict, primary failure, hypotheses, evidence windows, and
   missing signals render inline on the PR Checks page.
4. Exits non-zero when `DiagnosisPack.outcome.passed` is `false` (unless
   `fail-on-regression: false`).

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `bag` | yes | — | Path to a ROS2 bag directory or canonical `navigation_run.json`. |
| `config` | no | bundled `config/default.yaml` | Analyzer YAML/JSON config. |
| `output-dir` | no | `outputs/navigation-analyzer` | Where `analysis.json`, `report.md`, `diagnosis_pack.json`, and `diagnosis.md` are written. |
| `fail-on-regression` | no | `true` | When `true`, the step exits non-zero if any failure findings are detected. |
| `step-summary` | no | `true` | When `true`, `diagnosis.md` is appended to `GITHUB_STEP_SUMMARY`. |
| `python-version` | no | `3.12` | Python version for the analyzer environment. |

## Outputs

| Output | Description |
| --- | --- |
| `diagnosis-md-path` | Absolute path to `diagnosis.md`. |
| `diagnosis-pack-path` | Absolute path to `diagnosis_pack.json`. |
| `passed` | `true` or `false` from `outcome.passed`. |
| `primary-failure` | Primary failure type (empty when none). |
| `failure-count` | Number of `FailureFinding` records. |

## Uploading artifacts and posting PR comments

Combine the action with `actions/upload-artifact` to retain the JSON
artifacts and with `actions/github-script` or `gh pr comment` to post a
preview to PR conversations.

```yaml
- uses: rsasaki0109/NavigationAnalyzer@v0
  id: nav
  with:
    bag: artifacts/nav_smoke.json
    fail-on-regression: false

- name: Upload navigation artifacts
  uses: actions/upload-artifact@v4
  with:
    name: navigation-analyzer-${{ github.run_id }}
    path: outputs/navigation-analyzer

- name: Comment diagnosis on PR
  if: github.event_name == 'pull_request'
  uses: peter-evans/create-or-update-comment@v4
  with:
    issue-number: ${{ github.event.pull_request.number }}
    body-path: ${{ steps.nav.outputs.diagnosis-md-path }}
```

## Self-test

The CI workflow in this repository exercises `uses: ./` against three
zoo fixtures (`success_clean`, `oscillation_near_goal` with the gate
disabled, and `oscillation_near_goal` with the gate enabled) so any
breaking change to the action manifest fails fast.

## Versioning

Pin to `@v0` while the schema is still moving. A `@v1` tag will follow
once the DiagnosisPack schema is declared stable.
