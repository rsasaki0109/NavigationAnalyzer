import type { AnalysisArtifact } from "../types";

export async function loadAnalysis(): Promise<AnalysisArtifact> {
  const params = new URLSearchParams(window.location.search);
  const url = params.get("analysis") ?? "http://127.0.0.1:8000/analysis";
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load analysis from ${url}: ${response.status}`);
  }
  return response.json();
}
