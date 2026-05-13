import Plot from "react-plotly.js";
import type { AnalysisArtifact } from "../types";

type Props = {
  analysis: AnalysisArtifact;
  replayTime: number;
  selectedFailureKey: string | null;
  setReplayTime: (value: number) => void;
  setSelectedFailureKey: (value: string | null) => void;
};

function failureKey(failure: AnalysisArtifact["failures"][number]) {
  return `${failure.failure_type}-${failure.timestamp}`;
}

function formatValue(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "n/a";
  return JSON.stringify(value);
}

export function FailureTimeline({
  analysis,
  replayTime,
  selectedFailureKey,
  setReplayTime,
  setSelectedFailureKey,
}: Props) {
  const samples = analysis.run.samples;
  const min = samples[0]?.t ?? 0;
  const max = samples.at(-1)?.t ?? 1;
  const selectedFailure = analysis.failures.find((failure) => failureKey(failure) === selectedFailureKey) ?? null;
  const times = samples.map((sample) => sample.t);

  return (
    <section className="panel timelinePanel">
      <div className="panelHeader">
        <h2>Timeline Replay</h2>
        <output>{replayTime.toFixed(1)}s</output>
      </div>
      <input
        aria-label="Replay time"
        type="range"
        min={min}
        max={max}
        step="0.1"
        value={replayTime}
        onChange={(event) => setReplayTime(Number(event.currentTarget.value))}
      />
      <Plot
        data={[
          {
            type: "scatter",
            mode: "lines",
            name: "cmd_v",
            x: times,
            y: samples.map((sample) => sample.cmd_v),
            line: { color: "#276ef1", width: 2 },
          },
          {
            type: "scatter",
            mode: "lines",
            name: "cmd_w",
            x: times,
            y: samples.map((sample) => sample.cmd_w),
            line: { color: "#7c3aed", width: 2 },
          },
          {
            type: "scatter",
            mode: "lines",
            name: "goal_distance",
            x: times,
            y: samples.map((sample) => sample.goal_distance ?? Number.NaN),
            yaxis: "y2",
            line: { color: "#0b7a53", width: 2 },
          },
          {
            type: "scatter",
            mode: "lines",
            name: "obstacle_distance",
            x: times,
            y: samples.map((sample) => sample.obstacle_distance ?? Number.NaN),
            yaxis: "y2",
            line: { color: "#e67700", width: 2 },
          },
          {
            type: "scatter",
            mode: "markers",
            name: "failures",
            x: analysis.failures.map((failure) => failure.timestamp),
            y: analysis.failures.map(() => 0),
            marker: {
              color: analysis.failures.map((failure) => failure.severity === "high" ? "#c92a2a" : "#e67700"),
              size: analysis.failures.map((failure) => failureKey(failure) === selectedFailureKey ? 13 : 9),
              symbol: "diamond",
            },
            customdata: analysis.failures.map((failure) => failureKey(failure)),
            hovertemplate: "%{customdata}<extra></extra>",
          },
        ]}
        layout={{
          autosize: true,
          margin: { l: 42, r: 44, t: 8, b: 32 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          hovermode: "x unified",
          showlegend: true,
          legend: { orientation: "h", y: 1.16, x: 0 },
          xaxis: { title: { text: "time (s)" }, range: [min, max] },
          yaxis: { title: { text: "cmd" }, zeroline: true },
          yaxis2: { title: { text: "distance (m)" }, overlaying: "y", side: "right", rangemode: "tozero" },
          shapes: [
            {
              type: "line",
              x0: replayTime,
              x1: replayTime,
              y0: 0,
              y1: 1,
              yref: "paper",
              line: { color: "#111827", width: 2 },
            },
          ],
        }}
        onClick={(event) => {
          const point = event.points[0];
          if (!point) return;
          const key = point.customdata;
          if (typeof key === "string") {
            const failure = analysis.failures.find((item) => failureKey(item) === key);
            if (failure) {
              setSelectedFailureKey(key);
              setReplayTime(failure.timestamp);
            }
            return;
          }
          if (typeof point.x === "number") setReplayTime(point.x);
        }}
        useResizeHandler
        style={{ width: "100%", height: "310px" }}
        config={{ displayModeBar: false, responsive: true }}
      />
      <div className="failureList">
        {analysis.failures.length > 0 ? (
          analysis.failures.map((failure) => (
            <button
              className={failureKey(failure) === selectedFailureKey ? "selected" : ""}
              key={`${failure.failure_type}-${failure.timestamp}`}
              onClick={() => {
                setSelectedFailureKey(failureKey(failure));
                setReplayTime(failure.timestamp);
              }}
            >
              <span>{failure.failure_type}</span>
              <strong>{failure.timestamp.toFixed(1)}s</strong>
              <em data-severity={failure.severity}>{failure.severity}</em>
            </button>
          ))
        ) : (
          <div className="emptyState">No failure findings for this run.</div>
        )}
      </div>
      {selectedFailure ? (
        <div className="failureDetail">
          <div className="failureDetailHeader">
            <strong>{selectedFailure.failure_type}</strong>
            <span data-severity={selectedFailure.severity}>{selectedFailure.severity}</span>
          </div>
          <dl>
            <div>
              <dt>Timestamp</dt>
              <dd>{selectedFailure.timestamp.toFixed(3)}s</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{selectedFailure.confidence.toFixed(2)}</dd>
            </div>
            {Object.entries(selectedFailure.evidence).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{formatValue(value)}</dd>
              </div>
            ))}
          </dl>
          <div className="causeList">
            {selectedFailure.possible_causes.map((cause) => (
              <span key={cause}>{cause}</span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
