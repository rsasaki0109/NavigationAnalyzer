from pathlib import Path

import pytest

from navigation_analyzer.analysis import analyze_run
from navigation_analyzer.io import read_navigation_run
from navigation_analyzer.io.unitree_record_nav import read_unitree_record_nav_log
from navigation_analyzer.models import AnalyzerConfig


def test_unitree_record_nav_log_converts_contact_checked_run(tmp_path: Path):
    log = tmp_path / "isaac.log"
    log.write_text(
        "\n".join(
            [
                "[record_nav] goal marker: x=0.95 y=0.25 r=0.10",
                "[record_nav] frame 0/180  t=0.5s  pos=(-0.03,+0.01)  "
                "cmd=(+0.00,+0.00,+0.00)  cmd_count=0  min_clearance=+0.29  "
                "obstacle_overlaps=0  contact_ready=1  contact_events=0  "
                "max_contact_impulse=0.000000  contact_probe_failed=0",
                "[record_nav] frame 3/180  t=1.7s  pos=(+0.79,+0.11)  "
                "cmd=(+0.50,-0.20,-0.12)  cmd_count=82  min_clearance=+0.19  "
                "obstacle_overlaps=0  contact_ready=1  contact_events=0  "
                "max_contact_impulse=0.000000  contact_probe_failed=0",
            ]
        ),
        encoding="utf-8",
    )

    run = read_unitree_record_nav_log(log)

    assert run.goal is not None
    assert run.goal.x == pytest.approx(0.95)
    assert run.goal.y == pytest.approx(0.25)
    assert len(run.samples) == 2
    assert run.samples[-1].goal_distance == pytest.approx(0.2126, abs=0.001)
    assert run.samples[-1].cmd_v == pytest.approx(0.5385, abs=0.001)
    assert run.samples[-1].cmd_w == pytest.approx(-0.12)
    assert run.samples[-1].collision is False
    assert run.metadata["contact_probe_ready"] is True
    assert run.metadata["obstacle_contact_events"] == 0
    assert run.metadata["max_contact_impulse"] == 0.0


def test_reader_accepts_unitree_record_nav_log(tmp_path: Path):
    log = tmp_path / "isaac.log"
    log.write_text(
        "[record_nav] goal marker: x=1.0 y=0.0 r=0.10\n"
        "[record_nav] frame 0/10  t=0.0s  pos=(+0.00,+0.00)  "
        "cmd=(+0.00,+0.00,+0.00)  cmd_count=0  min_clearance=?  "
        "obstacle_overlaps=0\n",
        encoding="utf-8",
    )

    run = read_navigation_run(log)

    assert run.run_id == "isaac"
    assert run.samples[0].obstacle_distance is None


def test_unitree_record_nav_log_dogfood_analysis(tmp_path: Path):
    log = tmp_path / "isaac.log"
    log.write_text(
        "\n".join(
            [
                "[record_nav] goal marker: x=0.95 y=0.25 r=0.10",
                "[record_nav] frame 0/180  t=0.5s  pos=(-0.03,+0.01)  "
                "cmd=(+0.00,+0.00,+0.00)  cmd_count=0  min_clearance=+0.29  "
                "obstacle_overlaps=0  contact_ready=1  contact_events=0  "
                "max_contact_impulse=0.000000  contact_probe_failed=0",
                "[record_nav] frame 3/180  t=1.7s  pos=(+0.43,+0.06)  "
                "cmd=(+0.50,-0.20,-0.12)  cmd_count=82  min_clearance=+0.19  "
                "obstacle_overlaps=0  contact_ready=1  contact_events=0  "
                "max_contact_impulse=0.000000  contact_probe_failed=0",
                "[record_nav] frame 6/180  t=2.9s  pos=(+0.79,+0.11)  "
                "cmd=(+0.00,+0.00,+0.00)  cmd_count=132  min_clearance=+0.19  "
                "obstacle_overlaps=0  contact_ready=1  contact_events=0  "
                "max_contact_impulse=0.000000  contact_probe_failed=0",
            ]
        ),
        encoding="utf-8",
    )

    artifact = analyze_run(read_navigation_run(log), AnalyzerConfig(goal_tolerance_m=0.30))

    assert artifact.metrics["success_rate"].value == 1.0
    assert artifact.metrics["collision_count"].value == 0
    assert artifact.metrics["minimum_obstacle_distance"].value == pytest.approx(0.19)
    assert artifact.failures == []
