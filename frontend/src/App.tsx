import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, BarChart3, Gauge, Info, Upload } from "lucide-react";
import { BenchmarkDashboard } from "./components/BenchmarkDashboard";
import { FailureTimeline } from "./components/FailureTimeline";
import { MetricDashboard } from "./components/MetricDashboard";
import { TrajectoryScene } from "./components/TrajectoryScene";
import { loadAnalysis } from "./lib/api";
import type { AnalysisArtifact, BenchmarkArtifact, FailureFinding } from "./types";
import "./style.css";

function failureKey(failure: FailureFinding) {
  return `${failure.failure_type}-${failure.timestamp}`;
}

export default function App() {
  const [analysis, setAnalysis] = useState<AnalysisArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replayTime, setReplayTime] = useState(0);
  const [selectedFailureKey, setSelectedFailureKey] = useState<string | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkArtifact | null>(null);

  const selectFailure = useCallback((key: string, timestamp: number) => {
    setSelectedFailureKey(key);
    setReplayTime(timestamp);
  }, []);

  useEffect(() => {
    loadAnalysis()
      .then((artifact) => {
        setAnalysis(artifact);
        setReplayTime(artifact.run.samples[0]?.t ?? 0);
        setSelectedFailureKey(artifact.failures[0] ? failureKey(artifact.failures[0]) : null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const loadLocalFile = async (file: File) => {
    try {
      const payload = JSON.parse(await file.text()) as AnalysisArtifact;
      if (!payload.run?.samples || !payload.metrics || !Array.isArray(payload.failures)) {
        throw new Error("File is not a NavigationAnalyzer analysis artifact.");
      }
      setAnalysis(payload);
      setReplayTime(payload.run.samples[0]?.t ?? 0);
      setSelectedFailureKey(payload.failures[0] ? failureKey(payload.failures[0]) : null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load local analysis file.");
    }
  };

  const loadBenchmarkFile = async (file: File) => {
    try {
      const payload = JSON.parse(await file.text()) as BenchmarkArtifact;
      if (!Array.isArray(payload.runs) || !payload.summary || !payload.thresholds) {
        throw new Error("File is not a NavigationAnalyzer benchmark artifact.");
      }
      setBenchmark(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load local benchmark file.");
    }
  };

  if (error) {
    return <main className="status">Failed to load analysis: {error}</main>;
  }

  if (!analysis) {
    return <main className="status">Loading NavigationAnalyzer...</main>;
  }

  return (
    <main>
      <header className="appHeader">
        <div>
          <h1>NavigationAnalyzer</h1>
          <p>{analysis.run.run_id}</p>
        </div>
        <div className="headerStats">
          <label className="fileButton">
            <Upload size={17} />
            <span>Open analysis.json</span>
            <input
              type="file"
              accept="application/json,.json"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) void loadLocalFile(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <label className="fileButton">
            <BarChart3 size={17} />
            <span>Open benchmark.json</span>
            <input
              type="file"
              accept="application/json,.json"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) void loadBenchmarkFile(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <span><Gauge size={17} /> {analysis.metrics.success_rate.value}</span>
          <span><AlertTriangle size={17} /> {analysis.failures.length}</span>
          <span><Info size={17} /> {analysis.diagnostics?.length ?? 0}</span>
          <span><Activity size={17} /> {analysis.run.samples.length}</span>
        </div>
      </header>
      <section className="workspace">
        <div className="viewerColumn">
          <TrajectoryScene
            analysis={analysis}
            replayTime={replayTime}
            selectedFailureKey={selectedFailureKey}
            onSelectFailure={selectFailure}
          />
          <FailureTimeline
            analysis={analysis}
            replayTime={replayTime}
            selectedFailureKey={selectedFailureKey}
            setReplayTime={setReplayTime}
            setSelectedFailureKey={setSelectedFailureKey}
          />
        </div>
        <MetricDashboard analysis={analysis} />
      </section>
      {benchmark ? <BenchmarkDashboard benchmark={benchmark} /> : null}
    </main>
  );
}
