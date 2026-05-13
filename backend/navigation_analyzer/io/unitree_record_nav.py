from __future__ import annotations

import math
import re
from pathlib import Path

from navigation_analyzer.models import NavigationRun, NavigationSample, Point2D, Pose2D

_FLOAT = r"[+-]?\d+(?:\.\d+)?"

_GOAL_RE = re.compile(
    rf"\[record_nav\] goal marker: x=(?P<x>{_FLOAT}) y=(?P<y>{_FLOAT})"
)

_FRAME_RE = re.compile(
    rf"\[record_nav\] frame (?P<frame>\d+)/(?P<total>\d+)\s+"
    rf"t=(?P<t>{_FLOAT})s\s+"
    rf"pos=\((?P<x>{_FLOAT}),(?P<y>{_FLOAT})\)\s+"
    rf"cmd=\((?P<cmd_x>{_FLOAT}),(?P<cmd_y>{_FLOAT}),(?P<cmd_w>{_FLOAT})\)\s+"
    rf"cmd_count=(?P<cmd_count>\d+)\s+"
    rf"min_clearance=(?P<clearance>\?|{_FLOAT})\s+"
    rf"obstacle_overlaps=(?P<overlaps>\d+)"
    rf"(?:\s+contact_ready=(?P<contact_ready>\d+)\s+"
    rf"contact_events=(?P<contact_events>\d+)\s+"
    rf"max_contact_impulse=(?P<contact_impulse>{_FLOAT})\s+"
    rf"contact_probe_failed=(?P<contact_probe_failed>\d+))?"
)


def read_unitree_record_nav_log(path: Path, goal: Point2D | None = None) -> NavigationRun:
    """Convert unitree-nav-sim record_nav_demo.py logs to canonical samples."""

    text = path.read_text(encoding="utf-8", errors="replace")
    inferred_goal = goal or _goal_from_log(text)
    samples: list[NavigationSample] = []
    metadata = {
        "source_format": "unitree-nav-sim.record_nav_demo.log",
        "frame_count": 0,
        "total_frames": None,
        "max_cmd_count": 0,
        "max_obstacle_overlaps": 0,
        "contact_probe_ready": False,
        "contact_probe_failed": False,
        "obstacle_contact_events": 0,
        "max_contact_impulse": 0.0,
    }

    for match in _FRAME_RE.finditer(text):
        x = float(match.group("x"))
        y = float(match.group("y"))
        cmd_x = float(match.group("cmd_x"))
        cmd_y = float(match.group("cmd_y"))
        cmd_w = float(match.group("cmd_w"))
        clearance = _optional_float(match.group("clearance"))
        overlaps = int(match.group("overlaps"))
        contact_events = int(match.group("contact_events") or 0)
        contact_impulse = float(match.group("contact_impulse") or 0.0)
        contact_failed = int(match.group("contact_probe_failed") or 0)
        collided = overlaps > 0 or contact_events > 0 or contact_impulse > 0.0
        pose = Pose2D(x=x, y=y, yaw=0.0)
        samples.append(
            NavigationSample(
                t=float(match.group("t")),
                pose=pose,
                cmd_v=math.hypot(cmd_x, cmd_y),
                cmd_w=cmd_w,
                goal_distance=_goal_distance(pose, inferred_goal),
                obstacle_distance=clearance,
                collision=collided,
            )
        )
        metadata["frame_count"] += 1
        metadata["total_frames"] = int(match.group("total"))
        metadata["max_cmd_count"] = max(metadata["max_cmd_count"], int(match.group("cmd_count")))
        metadata["max_obstacle_overlaps"] = max(metadata["max_obstacle_overlaps"], overlaps)
        metadata["contact_probe_ready"] = metadata["contact_probe_ready"] or match.group("contact_ready") == "1"
        metadata["contact_probe_failed"] = metadata["contact_probe_failed"] or contact_failed == 1
        metadata["obstacle_contact_events"] = max(metadata["obstacle_contact_events"], contact_events)
        metadata["max_contact_impulse"] = max(metadata["max_contact_impulse"], contact_impulse)

    if not samples:
        raise ValueError(f"no record_nav_demo frame samples found in {path}")

    return NavigationRun(
        run_id=path.stem,
        source=str(path),
        goal=inferred_goal,
        samples=samples,
        metadata=metadata,
    )


def _goal_from_log(text: str) -> Point2D | None:
    match = _GOAL_RE.search(text)
    if match is None:
        return None
    return Point2D(x=float(match.group("x")), y=float(match.group("y")))


def _goal_distance(pose: Pose2D, goal: Point2D | None) -> float | None:
    if goal is None:
        return None
    return math.hypot(pose.x - goal.x, pose.y - goal.y)


def _optional_float(value: str) -> float | None:
    if value == "?":
        return None
    return float(value)
