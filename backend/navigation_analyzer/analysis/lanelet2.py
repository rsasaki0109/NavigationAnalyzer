from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from navigation_analyzer.models import NavigationRun, Point2D


@dataclass(frozen=True)
class LaneletMap:
    path: str
    lanelets: dict[int, tuple[Point2D, ...]]
    node_count: int
    way_count: int
    relation_count: int


def compute_route_lanelet_metrics(run: NavigationRun, map_path: Path | None) -> dict[str, float | int | None]:
    empty = {
        "final_centerline_distance": None,
        "mean_centerline_distance": None,
        "max_centerline_distance": None,
        "progress_ratio": None,
        "remaining_distance": None,
        "matched_lanelet_count": 0,
    }
    if map_path is None or not map_path.exists() or not run.samples:
        return empty

    preferred_ids = _preferred_lanelet_ids(run)
    if not preferred_ids:
        return empty

    lanelet_map = load_lanelet2_map(map_path)
    route_centerline: list[Point2D] = []
    matched = 0
    for lanelet_id in preferred_ids:
        centerline = lanelet_map.lanelets.get(lanelet_id)
        if not centerline:
            continue
        matched += 1
        if route_centerline and _distance(route_centerline[-1], centerline[0]) <= 1e-6:
            route_centerline.extend(centerline[1:])
        else:
            route_centerline.extend(centerline)

    if len(route_centerline) < 2:
        return {**empty, "matched_lanelet_count": matched}

    distances = [_distance_to_polyline(sample.pose, route_centerline) for sample in run.samples]
    final_projection = _project_onto_polyline(run.samples[-1].pose, route_centerline)
    route_length = _polyline_length(route_centerline)
    if final_projection is None or route_length <= 1e-6:
        return {**empty, "matched_lanelet_count": matched}

    return {
        "final_centerline_distance": distances[-1],
        "mean_centerline_distance": sum(distances) / len(distances),
        "max_centerline_distance": max(distances),
        "progress_ratio": max(0.0, min(1.0, final_projection[0] / route_length)),
        "remaining_distance": max(0.0, route_length - final_projection[0]),
        "matched_lanelet_count": matched,
    }


def load_lanelet2_map(path: Path) -> LaneletMap:
    return _load_lanelet2_map(str(path.resolve()))


@lru_cache(maxsize=8)
def _load_lanelet2_map(path: str) -> LaneletMap:
    root = ET.parse(path).getroot()
    nodes: dict[int, Point2D] = {}
    for node in root.findall("node"):
        node_id = int(node.attrib["id"])
        point = _node_point(node)
        if point is not None:
            nodes[node_id] = point

    ways: dict[int, list[Point2D]] = {}
    for way in root.findall("way"):
        way_id = int(way.attrib["id"])
        points = [nodes[int(nd.attrib["ref"])] for nd in way.findall("nd") if int(nd.attrib["ref"]) in nodes]
        if len(points) >= 2:
            ways[way_id] = points

    lanelets: dict[int, tuple[Point2D, ...]] = {}
    relation_count = 0
    for relation in root.findall("relation"):
        relation_count += 1
        tags = {tag.attrib.get("k"): tag.attrib.get("v") for tag in relation.findall("tag")}
        if tags.get("type") != "lanelet":
            continue

        relation_id = int(relation.attrib["id"])
        left_way = None
        right_way = None
        centerline_way = None
        for member in relation.findall("member"):
            if member.attrib.get("type") != "way":
                continue
            role = member.attrib.get("role")
            ref = int(member.attrib["ref"])
            if role == "left":
                left_way = ways.get(ref)
            elif role == "right":
                right_way = ways.get(ref)
            elif role == "centerline":
                centerline_way = ways.get(ref)

        if centerline_way:
            lanelets[relation_id] = tuple(centerline_way)
        elif left_way and right_way:
            lanelets[relation_id] = tuple(_centerline_from_bounds(left_way, right_way))

    return LaneletMap(
        path=path,
        lanelets=lanelets,
        node_count=len(nodes),
        way_count=len(ways),
        relation_count=relation_count,
    )


def _node_point(node: ET.Element) -> Point2D | None:
    tags = {tag.attrib.get("k"): tag.attrib.get("v") for tag in node.findall("tag")}
    x = tags.get("local_x") or tags.get("x")
    y = tags.get("local_y") or tags.get("y")
    if x is not None and y is not None:
        return Point2D(x=float(x), y=float(y))

    lat = node.attrib.get("lat")
    lon = node.attrib.get("lon")
    if lat is None or lon is None:
        return None
    easting, northing = _utm_xy(float(lat), float(lon))
    return Point2D(x=easting % 100000.0, y=northing % 100000.0)


def _preferred_lanelet_ids(run: NavigationRun) -> list[int]:
    route_summary = run.metadata.get("route_summary")
    if not isinstance(route_summary, dict):
        return []
    ids = route_summary.get("preferred_ids") or route_summary.get("primitive_ids")
    if not isinstance(ids, list):
        return []
    parsed = []
    for value in ids:
        if isinstance(value, int):
            parsed.append(value)
        elif isinstance(value, str) and value.isdigit():
            parsed.append(int(value))
    return parsed


def _centerline_from_bounds(left: list[Point2D], right: list[Point2D]) -> list[Point2D]:
    if _distance(left[0], right[0]) + _distance(left[-1], right[-1]) > _distance(left[0], right[-1]) + _distance(left[-1], right[0]):
        right = list(reversed(right))
    samples = max(len(left), len(right), 2)
    centerline = []
    for index in range(samples):
        ratio = index / (samples - 1)
        l_point = _interpolate_polyline(left, ratio)
        r_point = _interpolate_polyline(right, ratio)
        centerline.append(Point2D(x=(l_point.x + r_point.x) / 2.0, y=(l_point.y + r_point.y) / 2.0))
    return centerline


def _interpolate_polyline(points: list[Point2D], ratio: float) -> Point2D:
    if len(points) == 1:
        return points[0]
    total = _polyline_length(points)
    if total <= 1e-9:
        return points[0]
    target = max(0.0, min(1.0, ratio)) * total
    walked = 0.0
    for a, b in zip(points, points[1:]):
        segment = _distance(a, b)
        if walked + segment >= target:
            local = 0.0 if segment <= 1e-9 else (target - walked) / segment
            return Point2D(x=a.x + (b.x - a.x) * local, y=a.y + (b.y - a.y) * local)
        walked += segment
    return points[-1]


def _distance_to_polyline(point: Point2D, polyline: list[Point2D]) -> float:
    projection = _project_onto_polyline(point, polyline)
    return projection[1] if projection is not None else math.inf


def _project_onto_polyline(point: Point2D, polyline: list[Point2D]) -> tuple[float, float] | None:
    if len(polyline) < 2:
        return None
    best_along = 0.0
    best_distance = math.inf
    walked = 0.0
    for a, b in zip(polyline, polyline[1:]):
        vx = b.x - a.x
        vy = b.y - a.y
        length_sq = vx * vx + vy * vy
        if length_sq <= 1e-12:
            continue
        t = ((point.x - a.x) * vx + (point.y - a.y) * vy) / length_sq
        t = max(0.0, min(1.0, t))
        projected = Point2D(x=a.x + vx * t, y=a.y + vy * t)
        distance = _distance(point, projected)
        if distance < best_distance:
            best_distance = distance
            best_along = walked + math.sqrt(length_sq) * t
        walked += math.sqrt(length_sq)
    if math.isinf(best_distance):
        return None
    return best_along, best_distance


def _polyline_length(points: list[Point2D] | tuple[Point2D, ...]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _utm_xy(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    zone = int((lon_deg + 180.0) / 6.0) + 1
    lon_origin = (zone - 1) * 6.0 - 180.0 + 3.0
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    lon0 = math.radians(lon_origin)

    a = 6378137.0
    ecc_sq = 0.0066943799901413165
    ecc_prime_sq = ecc_sq / (1.0 - ecc_sq)
    k0 = 0.9996

    n = a / math.sqrt(1.0 - ecc_sq * math.sin(lat) ** 2)
    t = math.tan(lat) ** 2
    c = ecc_prime_sq * math.cos(lat) ** 2
    aa = math.cos(lat) * (lon - lon0)
    m = a * (
        (1 - ecc_sq / 4 - 3 * ecc_sq**2 / 64 - 5 * ecc_sq**3 / 256) * lat
        - (3 * ecc_sq / 8 + 3 * ecc_sq**2 / 32 + 45 * ecc_sq**3 / 1024) * math.sin(2 * lat)
        + (15 * ecc_sq**2 / 256 + 45 * ecc_sq**3 / 1024) * math.sin(4 * lat)
        - (35 * ecc_sq**3 / 3072) * math.sin(6 * lat)
    )

    easting = k0 * n * (
        aa
        + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t**2 + 72 * c - 58 * ecc_prime_sq) * aa**5 / 120
    ) + 500000.0
    northing = k0 * (
        m
        + n
        * math.tan(lat)
        * (
            aa**2 / 2
            + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * ecc_prime_sq) * aa**6 / 720
        )
    )
    if lat_deg < 0:
        northing += 10000000.0
    return easting, northing
