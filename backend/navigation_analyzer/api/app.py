from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from navigation_analyzer.models import AnalysisArtifact


def create_app(analysis_path: Path) -> FastAPI:
    app = FastAPI(title="NavigationAnalyzer API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def load_artifact() -> AnalysisArtifact:
        return AnalysisArtifact.model_validate_json(analysis_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/analysis")
    def analysis() -> dict:
        return load_artifact().model_dump(mode="json")

    @app.get("/metrics")
    def metrics() -> dict:
        return {key: value.model_dump(mode="json") for key, value in load_artifact().metrics.items()}

    @app.get("/failures")
    def failures() -> list[dict]:
        return [failure.model_dump(mode="json") for failure in load_artifact().failures]

    @app.get("/diagnostics")
    def diagnostics() -> list[dict]:
        return [diagnostic.model_dump(mode="json") for diagnostic in load_artifact().diagnostics]

    return app
