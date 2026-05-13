export type Point2D = { x: number; y: number };
export type Pose2D = Point2D & { yaw: number };

export type NavigationSample = {
  t: number;
  pose: Pose2D;
  cmd_v: number;
  cmd_w: number;
  goal_distance?: number | null;
  obstacle_distance?: number | null;
  collision: boolean;
  recovery_event: boolean;
  localization_error?: number | null;
};

export type MetricResult = {
  name: string;
  value: number | boolean | null;
  unit: string;
  description: string;
};

export type FailureFinding = {
  failure_type: string;
  timestamp: number;
  severity: "low" | "medium" | "high";
  confidence: number;
  evidence: Record<string, unknown>;
  possible_causes: string[];
};

export type AnalysisArtifact = {
  schema_version: string;
  run: {
    run_id: string;
    source: string;
    goal?: Point2D | null;
    goal_pose?: Pose2D | null;
    planned_path: Point2D[];
    samples: NavigationSample[];
    costmap?: {
      width: number;
      height: number;
      resolution: number;
      origin: Point2D;
      data: number[];
    } | null;
    metadata: Record<string, unknown>;
  };
  metrics: Record<string, MetricResult>;
  failures: FailureFinding[];
};

export type BenchmarkRun = {
  run_id: string;
  source: string;
  metrics: Record<string, number | boolean | null>;
  failures: FailureFinding[];
  final_sample?: NavigationSample | null;
  derived?: Record<string, number | string | boolean | null>;
};

export type BenchmarkViolation = {
  run_id: string;
  check: string;
  message: string;
};

export type BenchmarkMetricDelta = {
  run_id: string;
  metric: string;
  baseline: number;
  value: number;
  delta: number;
  delta_percent?: number | null;
  direction: "lower_is_better" | "higher_is_better" | "absolute_lower_is_better";
  regression: boolean;
  improvement: boolean;
};

export type BenchmarkArtifact = {
  schema_version: string;
  summary: {
    run_count: number;
    metric_means?: Record<string, number>;
    failure_type_counts?: Record<string, number>;
  };
  thresholds: {
    enabled: boolean;
    passed: boolean;
    profile: string;
    description?: string;
    violations: BenchmarkViolation[];
  };
  comparisons?: {
    baseline_run_id?: string | null;
    metric_deltas?: BenchmarkMetricDelta[];
  };
  runs: BenchmarkRun[];
};
