"""Per-part closure gate: open edges, non-manifold edges, winding, degeneracy."""

from __future__ import annotations

from beastforge.geometry.closure import ClosureReport, analyze_part
from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import ValidationFinding
from beastforge.validation.common import finding


def _path(name: str, part_names: set[str]) -> str:
    return f"parts[{name}]" if name in part_names else f"surfaces[{name}]"


def check_closure(
    mesh: Mesh,
    *,
    recipe_label: str,
    part_names: set[str] | None = None,
) -> list[ValidationFinding]:
    """Run the closure analyzer over every ``SurfaceRange`` in mesh order."""
    part_names = part_names or set()
    findings: list[ValidationFinding] = []
    for surface_range in mesh.surfaces:
        start = surface_range.vertex_offset
        end = start + surface_range.vertex_count
        index_end = surface_range.index_offset + surface_range.index_count
        local_positions = mesh.positions[start:end]
        local_indices = mesh.indices[surface_range.index_offset : index_end] - start
        report = analyze_part(local_positions, local_indices, surface_range.name)
        findings.extend(_findings(report, recipe_label, _path(surface_range.name, part_names)))
    return findings


def _findings(
    report: ClosureReport, recipe_label: str, path: str
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if report.boundary_edges:
        findings.append(
            finding(
                "surface-open",
                f"Part {report.name!r} has {report.boundary_edges} boundary edges; it is "
                "not watertight.",
                recipe=recipe_label,
                path=path,
                expected="every edge shared by exactly two faces",
                actual={
                    "boundary_edges": report.boundary_edges,
                    "first_edge": report.first_issue.get("edge")
                    if report.first_issue
                    else None,
                },
                remedy="Enable caps on the swept surface or raise rings/segments.",
            )
        )
    if report.non_manifold_edges:
        findings.append(
            finding(
                "surface-non-manifold",
                f"Part {report.name!r} has {report.non_manifold_edges} non-manifold edges.",
                recipe=recipe_label,
                path=path,
                expected="exactly two incident faces per edge",
                actual={
                    "non_manifold_edges": report.non_manifold_edges,
                    "first_edge": report.first_issue.get("edge")
                    if report.first_issue
                    else None,
                },
                remedy="Remove duplicated/overlapping faces or fix the construction.",
            )
        )
    if report.inconsistent_edges or report.signed_volume <= 0.0:
        detail: dict[str, object] = {
            "inconsistent_edges": report.inconsistent_edges,
            "signed_volume": report.signed_volume,
        }
        if report.inconsistent_edges and report.first_issue:
            detail["first_edge"] = report.first_issue.get("edge")
        findings.append(
            finding(
                "surface-winding-invalid",
                f"Part {report.name!r} is not consistently wound outward.",
                recipe=recipe_label,
                path=path,
                expected="consistent outward winding and positive signed volume",
                actual=detail,
                remedy="Reverse the part's triangle winding so normals point outward.",
            )
        )
    if report.degenerate_faces:
        findings.append(
            finding(
                "surface-degenerate",
                f"Part {report.name!r} has {report.degenerate_faces} degenerate faces.",
                recipe=recipe_label,
                path=path,
                expected="positive-area triangles with distinct vertices",
                actual={
                    "degenerate_faces": report.degenerate_faces,
                    "first_face": report.first_issue.get("face")
                    if report.first_issue
                    else None,
                },
                remedy="Raise rings/segments or reduce extreme taper/noise/scale.",
            )
        )
    return findings


__all__ = ["check_closure"]
