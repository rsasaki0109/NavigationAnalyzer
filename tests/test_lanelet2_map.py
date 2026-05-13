from pathlib import Path

import pytest

from navigation_analyzer.analysis.lanelet2 import compute_route_lanelet_metrics, load_lanelet2_map
from navigation_analyzer.models import NavigationRun, NavigationSample, Pose2D


def test_lanelet2_osm_centerline_metrics(tmp_path: Path):
    map_path = tmp_path / "lanelet2_map.osm"
    map_path.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6'>
  <node id='1'><tag k='local_x' v='0'/><tag k='local_y' v='2'/></node>
  <node id='2'><tag k='local_x' v='10'/><tag k='local_y' v='2'/></node>
  <node id='3'><tag k='local_x' v='0'/><tag k='local_y' v='0'/></node>
  <node id='4'><tag k='local_x' v='10'/><tag k='local_y' v='0'/></node>
  <way id='10'><nd ref='1'/><nd ref='2'/></way>
  <way id='20'><nd ref='3'/><nd ref='4'/></way>
  <relation id='100'>
    <member type='way' ref='10' role='left'/>
    <member type='way' ref='20' role='right'/>
    <tag k='type' v='lanelet'/>
    <tag k='subtype' v='road'/>
  </relation>
</osm>
""",
        encoding="utf-8",
    )
    lanelet_map = load_lanelet2_map(map_path)

    assert lanelet_map.lanelets[100][0].x == 0.0
    assert lanelet_map.lanelets[100][0].y == 1.0

    run = NavigationRun(
        run_id="lanelet-route",
        source="test",
        samples=[
            NavigationSample(t=0.0, pose=Pose2D(x=5.0, y=2.0, yaw=0.0)),
            NavigationSample(t=1.0, pose=Pose2D(x=10.0, y=1.2, yaw=0.0)),
        ],
        metadata={"route_summary": {"preferred_ids": [100]}},
    )

    metrics = compute_route_lanelet_metrics(run, map_path)

    assert metrics["matched_lanelet_count"] == 1
    assert metrics["final_centerline_distance"] == pytest.approx(0.2)
    assert metrics["mean_centerline_distance"] == pytest.approx(0.6)
    assert metrics["max_centerline_distance"] == pytest.approx(1.0)
    assert metrics["progress_ratio"] == pytest.approx(1.0)
    assert metrics["remaining_distance"] == pytest.approx(0.0)
