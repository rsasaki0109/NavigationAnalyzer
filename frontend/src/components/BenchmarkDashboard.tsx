import Plot from "react-plotly.js";
import { CheckCircle2, XCircle } from "lucide-react";
import type { BenchmarkArtifact, BenchmarkRun } from "../types";

const METRICS = [
  "success_rate",
  "goal_distance",
  "time_to_goal",
  "path_length",
  "collision_count",
  "oscillation_count",
  "recovery_count",
  "final_lateral_error",
  "final_longitudinal_error",
  "final_yaw_error",
  "final_stopped_duration",
];

type Props = {
  benchmark: BenchmarkArtifact;
};

function numberValue(run: BenchmarkRun, name: string): number | null {
  const value = run.metrics[name];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatValue(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    if (Math.abs(value) >= 100) return value.toFixed(1);
    if (Math.abs(value) >= 10) return value.toFixed(2);
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(3);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  return "n/a";
}

function runStatus(run: BenchmarkRun) {
  const success = numberValue(run, "success_rate") ?? 0;
  if (success >= 1 && run.failures.length === 0) return "pass";
  if (success >= 1) return "warn";
  return "fail";
}

export function BenchmarkDashboard({ benchmark }: Props) {
  const runs = benchmark.runs;
  const baselineRunId = benchmark.comparisons?.baseline_run_id ?? runs[0]?.run_id ?? null;
  const metricDeltas = benchmark.comparisons?.metric_deltas ?? buildLocalDeltas(runs);
  const candidateDeltas = metricDeltas.filter((delta) => delta.run_id !== baselineRunId);
  const regressions = candidateDeltas.filter((delta) => delta.regression);
  const improvements = candidateDeltas.filter((delta) => delta.improvement);
  const topDeltas = [...regressions, ...improvements].slice(0, 18);
  const bestGoal = runs.reduce<BenchmarkRun | null>((best, run) => {
    const value = numberValue(run, "goal_distance");
    if (value === null) return best;
    const bestValue = best ? numberValue(best, "goal_distance") : null;
    return bestValue === null || value < bestValue ? run : best;
  }, null);
  const shortestPath = runs.reduce<BenchmarkRun | null>((best, run) => {
    const value = numberValue(run, "path_length");
    if (value === null) return best;
    const bestValue = best ? numberValue(best, "path_length") : null;
    return bestValue === null || value < bestValue ? run : best;
  }, null);

  return (
    <section className="benchmarkPanel">
      <div className="benchmarkHeader">
        <div>
          <h2>Benchmark Comparison</h2>
          <p>{runs.length} runs · profile {benchmark.thresholds.profile}</p>
        </div>
        <div className={benchmark.thresholds.passed ? "benchmarkStatus pass" : "benchmarkStatus fail"}>
          {benchmark.thresholds.passed ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
          <span>{benchmark.thresholds.enabled ? (benchmark.thresholds.passed ? "passed" : "failed") : "comparison"}</span>
        </div>
      </div>

      <div className="benchmarkSummary">
        <div>
          <span>Best Goal Distance</span>
          <strong>{bestGoal ? bestGoal.run_id : "n/a"}</strong>
          <small>{bestGoal ? `${formatValue(bestGoal.metrics.goal_distance)} m` : ""}</small>
        </div>
        <div>
          <span>Shortest Path</span>
          <strong>{shortestPath ? shortestPath.run_id : "n/a"}</strong>
          <small>{shortestPath ? `${formatValue(shortestPath.metrics.path_length)} m` : ""}</small>
        </div>
        <div>
          <span>Failure Findings</span>
          <strong>{runs.reduce((total, run) => total + run.failures.length, 0)}</strong>
          <small>{Object.keys(benchmark.summary.failure_type_counts ?? {}).length} types</small>
        </div>
        <div>
          <span>Regressions</span>
          <strong>{regressions.length}</strong>
          <small>{baselineRunId ? `baseline ${baselineRunId}` : "no baseline"}</small>
        </div>
      </div>

      <div className="benchmarkChartGrid">
        <div className="panel">
          <h2>Run Metrics</h2>
          <Plot
            data={METRICS.map((metric) => ({
              type: "bar",
              name: metric,
              x: runs.map((run) => run.run_id),
              y: runs.map((run) => numberValue(run, metric)),
            }))}
            layout={{
              barmode: "group",
              autosize: true,
              margin: { l: 44, r: 12, t: 8, b: 92 },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              legend: { orientation: "h", y: 1.24, x: 0 },
            }}
            useResizeHandler
            style={{ width: "100%", height: "380px" }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
        <div className="panel">
          <h2>Failure Types</h2>
          <Plot
            data={[
              {
                type: "bar",
                orientation: "h",
                x: Object.values(benchmark.summary.failure_type_counts ?? {}),
                y: Object.keys(benchmark.summary.failure_type_counts ?? {}),
                marker: { color: "#c2410c" },
              },
            ]}
            layout={{
              autosize: true,
              margin: { l: 150, r: 12, t: 8, b: 36 },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
            }}
            useResizeHandler
            style={{ width: "100%", height: "380px" }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </div>

      <div className="benchmarkTableWrap">
        <table className="benchmarkTable">
          <thead>
            <tr>
              <th>Run</th>
              <th>Metric</th>
              <th>Baseline</th>
              <th>Value</th>
              <th>Delta</th>
              <th>Delta %</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {topDeltas.length > 0 ? (
              topDeltas.map((delta) => (
                <tr key={`${delta.run_id}-${delta.metric}`}>
                  <td><strong>{delta.run_id}</strong></td>
                  <td>{delta.metric}</td>
                  <td>{formatValue(delta.baseline)}</td>
                  <td>{formatValue(delta.value)}</td>
                  <td><span data-diff={delta.regression ? "regression" : "improvement"}>{formatSigned(delta.delta)}</span></td>
                  <td>{delta.delta_percent === null || delta.delta_percent === undefined ? "n/a" : `${formatSigned(delta.delta_percent)}%`}</td>
                  <td>{delta.direction}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7}>No regressions or improvements beyond the 5% comparison band.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="benchmarkTableWrap">
        <table className="benchmarkTable">
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Success</th>
              <th>Goal</th>
              <th>Time</th>
              <th>Path</th>
              <th>Collisions</th>
              <th>Failures</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td>
                  <strong>{run.run_id}</strong>
                  <small>{run.source}</small>
                </td>
                <td><span data-run-status={runStatus(run)}>{runStatus(run)}</span></td>
                <td>{formatValue(run.metrics.success_rate)}</td>
                <td>{formatValue(run.metrics.goal_distance)}</td>
                <td>{formatValue(run.metrics.time_to_goal)}</td>
                <td>{formatValue(run.metrics.path_length)}</td>
                <td>{formatValue(run.metrics.collision_count)}</td>
                <td>{run.failures.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {benchmark.thresholds.violations.length > 0 ? (
        <div className="violations">
          <h2>Threshold Violations</h2>
          {benchmark.thresholds.violations.map((violation) => (
            <div key={`${violation.run_id}-${violation.check}-${violation.message}`}>
              <strong>{violation.run_id}</strong>
              <span>{violation.check}</span>
              <p>{violation.message}</p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function formatSigned(value: number): string {
  const formatted = formatValue(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function buildLocalDeltas(runs: BenchmarkRun[]) {
  if (runs.length === 0) return [];
  const baseline = runs[0];
  return runs.flatMap((run) =>
    Array.from(new Set([...Object.keys(baseline.metrics), ...Object.keys(run.metrics), "failure_count"]))
      .map((metric) => {
        const baselineValue = metric === "failure_count" ? baseline.failures.length : numberValue(baseline, metric);
        const value = metric === "failure_count" ? run.failures.length : numberValue(run, metric);
        if (baselineValue === null || value === null) return null;
        const delta = value - baselineValue;
        const direction = metricDirection(metric);
        return {
          run_id: run.run_id,
          metric,
          baseline: baselineValue,
          value,
          delta,
          delta_percent: Math.abs(baselineValue) < 1e-9 ? null : (delta / Math.abs(baselineValue)) * 100,
          direction,
          regression: isRegression(baselineValue, value, direction),
          improvement: isImprovement(baselineValue, value, direction),
        };
      })
      .filter((delta) => delta !== null),
  );
}

function metricDirection(metric: string) {
  if (metric === "success_rate" || metric === "minimum_obstacle_distance" || metric === "final_stopped_duration") {
    return "higher_is_better";
  }
  if (metric === "final_lateral_error" || metric === "final_longitudinal_error" || metric === "final_yaw_error") {
    return "absolute_lower_is_better";
  }
  return "lower_is_better";
}

function isRegression(baseline: number, value: number, direction: ReturnType<typeof metricDirection>) {
  if (direction === "higher_is_better") return value < baseline * 0.95 - 1e-9;
  if (direction === "absolute_lower_is_better") return Math.abs(value) > Math.abs(baseline) * 1.05 + 1e-9;
  return value > baseline * 1.05 + 1e-9;
}

function isImprovement(baseline: number, value: number, direction: ReturnType<typeof metricDirection>) {
  if (direction === "higher_is_better") return value > baseline * 1.05 + 1e-9;
  if (direction === "absolute_lower_is_better") return Math.abs(value) < Math.abs(baseline) * 0.95 - 1e-9;
  return value < baseline * 0.95 - 1e-9;
}
