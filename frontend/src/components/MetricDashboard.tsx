import Plot from "react-plotly.js";
import type { AnalysisArtifact } from "../types";

function formatMetric(value: unknown) {
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

export function MetricDashboard({ analysis }: { analysis: AnalysisArtifact }) {
  const metricEntries = Object.values(analysis.metrics);
  const numeric = metricEntries.filter((metric) => typeof metric.value === "number");
  const samples = analysis.run.samples;
  const diagnostics = analysis.diagnostics ?? [];
  const routeSummary = analysis.run.metadata.route_summary;
  const route = isRouteSummary(routeSummary) ? routeSummary : null;

  return (
    <div className="dashboardGrid">
      {diagnostics.length ? (
        <section className="panel">
          <h2>Diagnostics</h2>
          <div className="diagnosticList">
            {diagnostics.map((diagnostic) => (
              <article key={`${diagnostic.diagnostic_type}-${diagnostic.timestamp}`} data-level={diagnostic.level}>
                <div>
                  <strong>{diagnostic.diagnostic_type}</strong>
                  <span>{diagnostic.level}</span>
                </div>
                <p>{diagnostic.summary}</p>
                <small>{formatMetric(diagnostic.timestamp)}s · confidence {formatMetric(diagnostic.confidence)}</small>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {route ? (
        <section className="panel">
          <h2>Route Summary</h2>
          <div className="routeSummary">
            <div>
              <span>Segments</span>
              <strong>{route.segment_count}</strong>
            </div>
            <div>
              <span>Primitives</span>
              <strong>{route.primitive_count}</strong>
            </div>
            <div>
              <span>Unique</span>
              <strong>{route.unique_primitive_count}</strong>
            </div>
            <div>
              <span>Route Topic</span>
              <strong>{String(analysis.run.metadata.route_topic ?? "n/a")}</strong>
            </div>
          </div>
          <div className="routeIds">
            {route.preferred_ids.slice(0, 24).map((id) => (
              <span key={id}>{id}</span>
            ))}
          </div>
        </section>
      ) : null}
      <section className="panel">
        <h2>Metrics</h2>
        <div className="metricGrid">
          {metricEntries.map((metric) => (
            <div className="metric" key={metric.name} title={metric.description}>
              <span>{metric.name}</span>
              <strong>{formatMetric(metric.value)}</strong>
              <small>{metric.unit}</small>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Metric Profile</h2>
        <Plot
          data={[
            {
              type: "bar",
              x: numeric.map((metric) => metric.name),
              y: numeric.map((metric) => metric.value as number),
              marker: { color: "#276ef1" },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 42, r: 12, t: 10, b: 80 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
          }}
          useResizeHandler
          style={{ width: "100%", height: "320px" }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </section>
      <section className="panel wide">
        <h2>Obstacle Distance Heatmap</h2>
        <Plot
          data={[
            {
              type: "scatter",
              mode: "lines+markers",
              x: samples.map((sample) => sample.pose.x),
              y: samples.map((sample) => sample.pose.y),
              marker: {
                size: 11,
                color: samples.map((sample) => sample.obstacle_distance ?? 1.5),
                colorscale: "Viridis",
                colorbar: { title: { text: "m" } },
              },
              line: { color: "#0b7a53" },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 42, r: 12, t: 10, b: 42 },
            xaxis: { title: { text: "x (m)" }, scaleanchor: "y" },
            yaxis: { title: { text: "y (m)" } },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
          }}
          useResizeHandler
          style={{ width: "100%", height: "360px" }}
          config={{ displayModeBar: true, responsive: true }}
        />
      </section>
    </div>
  );
}

function isRouteSummary(value: unknown): value is {
  segment_count: number;
  primitive_count: number;
  unique_primitive_count: number;
  preferred_ids: number[];
} {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.segment_count === "number"
    && typeof candidate.primitive_count === "number"
    && typeof candidate.unique_primitive_count === "number"
    && Array.isArray(candidate.preferred_ids)
  );
}
