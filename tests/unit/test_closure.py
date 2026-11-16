"""Closure-analyzer unit tests on hand-built meshes (FR-001, closure.md §4)."""

from __future__ import annotations

from beastforge.geometry.closure import analyze_part
from tests.fixtures import meshes


def test_closed_box_at_large_and_tiny_scale() -> None:
    for scale in (1e3, 1.0, 1e-4):
        positions, indices = meshes.closed_box(scale)
        report = analyze_part(positions, indices, "box")
        assert report.closed is True, (scale, report)
        assert report.boundary_edges == 0
        assert report.non_manifold_edges == 0
        assert report.inconsistent_edges == 0
        assert report.degenerate_faces == 0
        assert report.signed_volume > 0.0


def test_open_box_reports_boundary_edges() -> None:
    positions, indices = meshes.open_box()
    report = analyze_part(positions, indices, "open-box")
    assert report.closed is False
    assert report.boundary_edges > 0
    assert report.first_issue is not None
    assert report.first_issue["kind"] == "boundary"


def test_non_manifold_edge_is_reported() -> None:
    positions, indices = meshes.non_manifold_mesh()
    report = analyze_part(positions, indices, "non-manifold")
    assert report.closed is False
    assert report.non_manifold_edges > 0
    assert report.first_issue is not None
    assert report.first_issue["kind"] == "non-manifold"


def test_inward_winding_has_negative_volume() -> None:
    positions, indices = meshes.inward_box()
    report = analyze_part(positions, indices, "inward")
    assert report.closed is False
    assert report.inconsistent_edges == 0
    assert report.signed_volume < 0.0


def test_repeated_vertex_and_zero_area_triangles_are_degenerate() -> None:
    positions, indices = meshes.repeated_vertex_triangle()
    report = analyze_part(positions, indices, "repeated")
    assert report.degenerate_faces > 0

    positions, indices = meshes.zero_area_triangle()
    report = analyze_part(positions, indices, "zero-area")
    assert report.degenerate_faces > 0


def test_scale_relative_epsilon_rejects_collapsed_cap() -> None:
    positions, indices = meshes.closed_box()
    collapsed = positions.copy()
    collapsed[1] = collapsed[0]
    report = analyze_part(collapsed, indices, "collapsed")
    assert report.degenerate_faces > 0
