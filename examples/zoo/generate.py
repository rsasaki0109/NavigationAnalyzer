"""Generate the NavigationAnalyzer failure zoo fixtures.

Each fixture is tuned to trip exactly one rule (or, for the clean baseline,
none). Run from the repository root:

    python3 examples/zoo/generate.py

Outputs land at examples/zoo/<name>/navigation_run.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ZOO_DIR = Path(__file__).resolve().parent


@dataclass
class Sample:
    t: float
    x: float
    y: float
    yaw: float = 0.0
    cmd_v: float = 0.0
    cmd_w: float = 0.0
    goal_distance: float | None = None
    obstacle_distance: float | None = 1.5
    collision: bool = False
    recovery_event: bool = False
    localization_error: float | None = 0.05
    tf_age_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "t": self.t,
            "pose": {"x": self.x, "y": self.y, "yaw": self.yaw},
            "cmd_v": self.cmd_v,
            "cmd_w": self.cmd_w,
            "goal_distance": self.goal_distance,
            "obstacle_distance": self.obstacle_distance,
            "collision": self.collision,
            "recovery_event": self.recovery_event,
            "localization_error": self.localization_error,
            "tf_age_s": self.tf_age_s,
        }


def _write(name: str, payload: dict[str, Any]) -> Path:
    folder = ZOO_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "navigation_run.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _dist(x: float, y: float, gx: float, gy: float) -> float:
    return ((x - gx) ** 2 + (y - gy) ** 2) ** 0.5


def _line_path(gx: float, gy: float, steps: int = 21) -> list[dict[str, float]]:
    return [{"x": gx * i / (steps - 1), "y": gy * i / (steps - 1)} for i in range(steps)]


def build_success_clean() -> dict[str, Any]:
    goal = (5.0, 0.0)
    samples = []
    for i in range(11):
        t = float(i)
        x = min(5.0, 0.5 * i)
        samples.append(
            Sample(
                t=t,
                x=x,
                y=0.0,
                yaw=0.0,
                cmd_v=0.5 if x < goal[0] else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.5,
                localization_error=0.05,
            )
        )
    return {
        "run_id": "zoo_success_clean",
        "source": "examples/zoo/success_clean/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "clean straight-line success"},
    }


def build_oscillation() -> dict[str, Any]:
    goal = (5.0, 0.0)
    samples: list[Sample] = []
    # Move forward 0..10 to (4.0, 0.0).
    for i in range(11):
        x = 0.4 * i
        samples.append(
            Sample(
                t=float(i),
                x=x,
                y=0.0,
                yaw=0.0,
                cmd_v=0.4 if x < 4.0 else 0.06,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.4,
            )
        )
    # Oscillate at (4.0, 0.0): 10 samples flipping cmd_w sign, low cmd_v.
    for j in range(10):
        t = 11.0 + j
        yaw = 0.25 if j % 2 == 0 else -0.25
        cmd_w = 0.45 if j % 2 == 0 else -0.45
        samples.append(
            Sample(
                t=t,
                x=4.0,
                y=0.0,
                yaw=yaw,
                cmd_v=0.06,
                cmd_w=cmd_w,
                goal_distance=1.0,
                obstacle_distance=1.4,
            )
        )
    return {
        "run_id": "zoo_oscillation_near_goal",
        "source": "examples/zoo/oscillation_near_goal/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "controller oscillates near goal"},
    }


def build_deadlock() -> dict[str, Any]:
    goal = (10.0, 0.0)
    samples: list[Sample] = []
    # Move to (2,0) over 5s.
    for i in range(6):
        x = 0.4 * i
        samples.append(
            Sample(
                t=float(i),
                x=x,
                y=0.0,
                cmd_v=0.4 if x < 2.0 else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
            )
        )
    # Frozen 15s at (2,0).
    for j in range(1, 16):
        samples.append(
            Sample(
                t=6.0 + j,
                x=2.0,
                y=0.0,
                cmd_v=0.0,
                cmd_w=0.0,
                goal_distance=_dist(2.0, 0.0, *goal),
            )
        )
    return {
        "run_id": "zoo_deadlock",
        "source": "examples/zoo/deadlock/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "robot stalled mid-way"},
    }


def build_localization_drift() -> dict[str, Any]:
    goal = (5.0, 0.0)
    samples: list[Sample] = []
    for i in range(11):
        x = min(5.0, 0.5 * i)
        # Rises linearly from 0.05 to 0.85.
        drift = 0.05 + 0.08 * i
        samples.append(
            Sample(
                t=float(i),
                x=x,
                y=0.0,
                cmd_v=0.5 if x < goal[0] else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                localization_error=drift,
            )
        )
    return {
        "run_id": "zoo_localization_drift",
        "source": "examples/zoo/localization_drift/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "localization drifts during otherwise normal motion"},
    }


def build_dynamic_obstacle_freeze() -> dict[str, Any]:
    goal = (10.0, 0.0)
    samples: list[Sample] = []
    # Move from 0..3 over t=0..5.
    for i in range(6):
        x = 0.6 * i
        samples.append(
            Sample(
                t=float(i),
                x=x,
                y=0.0,
                cmd_v=0.6,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.2,
            )
        )
    # Freeze near (3, 0) for 5s with obstacle in 0.18..0.6 range. Below deadlock_duration_s=8.
    for j in range(1, 6):
        samples.append(
            Sample(
                t=5.0 + j,
                x=3.0,
                y=0.0,
                cmd_v=0.0,
                cmd_w=0.0,
                goal_distance=_dist(3.0, 0.0, *goal),
                obstacle_distance=0.4,
            )
        )
    # Resume and reach the goal.
    for i in range(11):
        x = 3.0 + 0.7 * i
        if x > goal[0]:
            x = goal[0]
        samples.append(
            Sample(
                t=11.0 + i,
                x=x,
                y=0.0,
                cmd_v=0.7 if x < goal[0] else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.2,
            )
        )
    return {
        "run_id": "zoo_dynamic_obstacle_freeze",
        "source": "examples/zoo/dynamic_obstacle_freeze/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "freezes near a stationary obstacle, then recovers"},
    }


def build_planner_divergence() -> dict[str, Any]:
    goal = (10.0, 0.0)
    samples: list[Sample] = []
    for i in range(21):
        t = float(i) * 0.5
        progress = i / 20.0
        # Detour through (5, 2.5).
        if progress <= 0.5:
            x = 5.0 * (progress / 0.5)
            y = 2.5 * (progress / 0.5)
        else:
            x = 5.0 + 5.0 * ((progress - 0.5) / 0.5)
            y = 2.5 * (1.0 - (progress - 0.5) / 0.5)
        samples.append(
            Sample(
                t=t,
                x=x,
                y=y,
                cmd_v=0.6 if progress < 1.0 else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, y, *goal),
                obstacle_distance=1.4,
            )
        )
    return {
        "run_id": "zoo_planner_divergence",
        "source": "examples/zoo/planner_divergence/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {"stack": "nav2", "scenario": "trajectory detours far from the planned path"},
    }


def build_nav2_yaw_violation() -> dict[str, Any]:
    """Nav2 SimpleGoalChecker yaw tolerance violation: xy passes, yaw fails."""

    goal = (5.0, 0.0)
    goal_yaw = 0.0
    samples: list[Sample] = []
    for i in range(11):
        t = float(i)
        x = min(5.0, 0.5 * i)
        # Final pose yaw climbs to 0.5 rad (violates 0.25 rad tolerance).
        yaw = 0.0 if x < 4.8 else 0.5
        samples.append(
            Sample(
                t=t,
                x=x,
                y=0.0,
                yaw=yaw,
                cmd_v=0.5 if x < goal[0] else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.4,
            )
        )
    return {
        "run_id": "zoo_nav2_yaw_violation",
        "source": "examples/zoo/nav2_yaw_violation/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": goal_yaw},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {
            "stack": "nav2",
            "scenario": "xy goal tolerance satisfied but yaw exceeds Nav2 SimpleGoalChecker default",
        },
    }


def build_tf_dropout() -> dict[str, Any]:
    """TF chain stalls mid-run: localization stops publishing while motion continues."""

    goal = (5.0, 0.0)
    samples: list[Sample] = []
    for i in range(21):
        t = float(i) * 0.5  # 0.5s spacing, 21 samples → 10s run
        x = min(5.0, 0.25 * i)
        # tf_age is healthy at the start (~0.05s), spikes to ~0.9s during 4-7s, recovers after.
        if 4.0 <= t <= 7.0:
            tf_age = 0.55 + 0.1 * (t - 4.0)
        else:
            tf_age = 0.05
        samples.append(
            Sample(
                t=t,
                x=x,
                y=0.0,
                cmd_v=0.5 if x < goal[0] else 0.0,
                cmd_w=0.0,
                goal_distance=_dist(x, 0.0, *goal),
                obstacle_distance=1.4,
                tf_age_s=tf_age,
            )
        )
    return {
        "run_id": "zoo_tf_dropout",
        "source": "examples/zoo/tf_dropout/navigation_run.json",
        "goal": {"x": goal[0], "y": goal[1]},
        "goal_pose": {"x": goal[0], "y": goal[1], "yaw": 0.0},
        "planned_path": _line_path(*goal),
        "samples": [s.to_dict() for s in samples],
        "metadata": {
            "stack": "nav2",
            "scenario": "TF chain stalls for ~3s mid-run while the robot keeps moving",
        },
    }


FIXTURES = {
    "success_clean": build_success_clean,
    "oscillation_near_goal": build_oscillation,
    "deadlock": build_deadlock,
    "localization_drift": build_localization_drift,
    "dynamic_obstacle_freeze": build_dynamic_obstacle_freeze,
    "planner_divergence": build_planner_divergence,
    "nav2_yaw_violation": build_nav2_yaw_violation,
    "tf_dropout": build_tf_dropout,
}


def main() -> None:
    for name, builder in FIXTURES.items():
        path = _write(name, builder())
        print(f"wrote {path.relative_to(ZOO_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
