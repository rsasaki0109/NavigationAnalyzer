from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Point2D(BaseModel):
    x: float
    y: float


class Pose2D(Point2D):
    yaw: float = 0.0


class NavigationSample(BaseModel):
    t: float = Field(description="Timestamp in seconds, relative or bag time.")
    pose: Pose2D
    cmd_v: float = 0.0
    cmd_w: float = 0.0
    goal_distance: float | None = None
    obstacle_distance: float | None = None
    collision: bool = False
    recovery_event: bool = False
    localization_error: float | None = None


class Costmap(BaseModel):
    width: int
    height: int
    resolution: float
    origin: Point2D = Field(default_factory=lambda: Point2D(x=0.0, y=0.0))
    data: list[float]


class NavigationRun(BaseModel):
    run_id: str
    source: str
    goal: Point2D | None = None
    goal_pose: Pose2D | None = None
    planned_path: list[Point2D] = Field(default_factory=list)
    samples: list[NavigationSample]
    costmap: Costmap | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_goal_aliases(self) -> "NavigationRun":
        if self.goal_pose is None and self.goal is not None:
            self.goal_pose = Pose2D(x=self.goal.x, y=self.goal.y, yaw=0.0)
        if self.goal is None and self.goal_pose is not None:
            self.goal = Point2D(x=self.goal_pose.x, y=self.goal_pose.y)
        return self


class MetricResult(BaseModel):
    name: str
    value: float | int | bool | None
    unit: str = ""
    description: str


class FailureFinding(BaseModel):
    failure_type: str
    timestamp: float
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    possible_causes: list[str] = Field(default_factory=list)


class RosbagTopicConfig(BaseModel):
    tf: list[str] = Field(default_factory=lambda: ["/tf"])
    localization_pose: list[str] = Field(default_factory=lambda: ["/amcl_pose", "/pose", "/localization_pose"])
    odometry: list[str] = Field(default_factory=lambda: ["/odom", "/odometry/filtered", "/localization/kinematic_state"])
    cmd_vel: list[str] = Field(default_factory=lambda: ["/cmd_vel", "/cmd_vel_nav", "/cmd_vel_smoothed"])
    scan: list[str] = Field(default_factory=lambda: ["/scan", "/front/scan"])
    pointcloud: list[str] = Field(default_factory=lambda: ["/points", "/pointcloud", "/velodyne_points"])
    plan: list[str] = Field(default_factory=lambda: ["/plan", "/global_plan", "/planner_server/plan"])
    trajectory: list[str] = Field(default_factory=lambda: ["/local_plan", "/trajectory", "/controller_server/trajectory"])
    costmap: list[str] = Field(default_factory=lambda: ["/global_costmap/costmap", "/local_costmap/costmap", "/costmap"])
    goal: list[str] = Field(default_factory=lambda: ["/goal_pose", "/goal"])
    recovery: list[str] = Field(default_factory=lambda: ["/behavior_server/transition_event", "/recoveries", "/recovery_status"])


class AnalyzerConfig(BaseModel):
    lanelet2_map: Path | None = Field(
        default=None,
        description="Optional lanelet2 OSM map used for Autoware route/lanelet-aware metrics.",
    )
    goal_tolerance_m: float = 0.5
    collision_distance_m: float = 0.18
    oscillation_window_s: float = 6.0
    oscillation_sign_changes: int = 5
    deadlock_speed_mps: float = 0.04
    deadlock_duration_s: float = 8.0
    deadlock_goal_distance_m: float = 1.0
    localization_drift_m: float = 0.7
    narrow_passage_distance_m: float = 0.35
    planner_divergence_m: float = 1.2
    rosbag_topics: RosbagTopicConfig = Field(default_factory=RosbagTopicConfig)


class AnalysisArtifact(BaseModel):
    schema_version: str = "navigation-analyzer.analysis.v1"
    run: NavigationRun
    metrics: dict[str, MetricResult]
    failures: list[FailureFinding]

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
