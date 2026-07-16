"""tests/test_geometry.py -- GeometryWorker structural + math tests.

Verifies the geometry engine produces correct results for known
inputs and rejects invalid arguments gracefully.
"""

import asyncio
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.math_pillar.geometry import GeometryWorker
from minxg.base import BaseWorker


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture
def w():
    return GeometryWorker()


def test_subclass():
    assert issubclass(GeometryWorker, BaseWorker)


def test_worker_id():
    assert GeometryWorker().worker_id == "geometry_tools"


def test_tier():
    assert GeometryWorker().tier == "code"


# ── Points ──

def test_distance(w):
    assert _run(w.distance([0, 0], [3, 4]))["distance"] == 5.0


def test_distance_3d(w):
    assert _run(w.distance([0, 0, 0], [1, 2, 2]))["distance"] == 3.0


def test_distance_mismatch(w):
    r = _run(w.distance([0, 0], [1]))
    assert r["status"] == "error"


def test_midpoint(w):
    assert _run(w.midpoint([0, 0], [4, 6]))["midpoint"] == [2.0, 3.0]


def test_centroid(w):
    r = _run(w.centroid([[0, 0], [2, 0], [0, 2], [2, 2]]))
    assert r["centroid"] == [1.0, 1.0]


def test_centroid_empty(w):
    assert _run(w.centroid([]))["status"] == "error"


def test_bounding_box(w):
    r = _run(w.bounding_box([[0, 0], [3, 4], [1, -2]]))
    assert r["min"] == [0, -2]
    assert r["max"] == [3, 4]
    assert r["size"] == [3, 6]


# ── Segments ──

def test_segment_length(w):
    assert _run(w.segment_length([0, 0], [3, 4]))["length"] == 5.0


def test_slope(w):
    assert _run(w.slope([0, 0], [2, 6]))["slope"] == 3.0


def test_slope_vertical(w):
    assert _run(w.slope([0, 0], [0, 5]))["slope"] == math.inf


def test_closest_point_mid(w):
    r = _run(w.closest_point_on_segment([0, 0], [4, 0], [2, 3]))
    assert r["closest"] == [2.0, 0.0]


def test_closest_point_endpoint(w):
    r = _run(w.closest_point_on_segment([0, 0], [4, 0], [-1, 3]))
    assert r["closest"] == [0.0, 0.0]


# ── Polygons ──

def test_perimeter(w):
    # unit square
    r = _run(w.polygon_perimeter([[0, 0], [1, 0], [1, 1], [0, 1]]))
    assert r["perimeter"] == 4.0


def test_polygon_area(w):
    # unit square
    r = _run(w.polygon_area([[0, 0], [1, 0], [1, 1], [0, 1]]))
    assert abs(r["area"] - 1.0) < 1e-12


def test_polygon_area_triangle(w):
    r = _run(w.polygon_area([[0, 0], [4, 0], [0, 3]]))
    assert abs(r["area"] - 6.0) < 1e-12


def test_convex_hull(w):
    pts = [[0, 0], [1, 0], [1, 1], [0, 1], [0.5, 0.5]]
    r = _run(w.convex_hull(pts))
    assert r["hull_size"] == 4
    # the interior point (0.5, 0.5) must NOT be in the hull
    for h in r["hull"]:
        assert h != (0.5, 0.5)
        assert h != [0.5, 0.5]


def test_point_in_polygon_inside(w):
    r = _run(w.point_in_polygon([0.5, 0.5], [[0, 0], [1, 0], [1, 1], [0, 1]]))
    assert r["inside"] is True


def test_point_in_polygon_outside(w):
    r = _run(w.point_in_polygon([2, 2], [[0, 0], [1, 0], [1, 1], [0, 1]]))
    assert r["inside"] is False


# ── Circles & spheres ──

def test_circle_circumference(w):
    r = _run(w.circle_circumference(1))
    assert abs(r["circumference"] - 2 * math.pi) < 1e-12


def test_circle_area(w):
    r = _run(w.circle_area(2))
    assert abs(r["area"] - 4 * math.pi) < 1e-12


def test_sphere_surface_area(w):
    r = _run(w.sphere_surface_area(1))
    assert abs(r["surface_area"] - 4 * math.pi) < 1e-12


def test_sphere_volume(w):
    r = _run(w.sphere_volume(1))
    expected = (4 / 3) * math.pi
    assert abs(r["volume"] - expected) < 1e-12


def test_negative_radius(w):
    assert _run(w.circle_area(-1))["status"] == "error"


# ── 3D ──

def test_triangle_area_3d(w):
    r = _run(w.triangle_area_3d([0, 0, 0], [1, 0, 0], [0, 1, 0]))
    assert abs(r["area"] - 0.5) < 1e-12


def test_tetrahedron_volume(w):
    r = _run(w.tetrahedron_volume([0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]))
    assert abs(r["volume"] - 1 / 6) < 1e-12


def test_surface_normal(w):
    r = _run(w.surface_normal([0, 0, 0], [1, 0, 0], [0, 1, 0]))
    n = r["normal"]
    assert abs(n[0]) < 1e-12
    assert abs(n[1]) < 1e-12
    assert abs(n[2] - 1.0) < 1e-12


# ── Transforms ──

def test_rotate_2d(w):
    r = _run(w.rotate_2d(1, 0, math.pi / 2))
    assert abs(r["point"][0]) < 1e-12
    assert abs(r["point"][1] - 1.0) < 1e-12


def test_rotate_x(w):
    r = _run(w.rotate_x(0, 1, 0, math.pi / 2))
    assert abs(r["point"][1]) < 1e-12
    assert abs(r["point"][2] - 1.0) < 1e-12


def test_rotate_y(w):
    r = _run(w.rotate_y(1, 0, 0, math.pi / 2))
    assert abs(r["point"][0]) < 1e-12
    assert abs(r["point"][2] + 1.0) < 1e-12


def test_rotate_z(w):
    r = _run(w.rotate_z(1, 0, 0, math.pi / 2))
    assert abs(r["point"][0]) < 1e-12
    assert abs(r["point"][1] - 1.0) < 1e-12


def test_scale(w):
    assert _run(w.scale([1, 2, 3], [2, 2, 2]))["point"] == [2, 4, 6]


def test_translate(w):
    assert _run(w.translate([1, 2], [10, 20]))["point"] == [11, 22]


def test_scale_mismatch(w):
    assert _run(w.scale([1, 2], [1]))["status"] == "error"
