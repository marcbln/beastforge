"""Single validation gate (research D11, FR-034..FR-038)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from beastforge.config import Settings, find_library_root
from beastforge.geometry.mesh import Mesh
from beastforge.model.errors import BeastforgeError
from beastforge.model.findings import ValidationFinding
from beastforge.model.manifest import Manifest
from beastforge.model.parts import ResolvedPart
from beastforge.model.recipe import Recipe
from beastforge.params import resolve_params
from beastforge.parts.registry import PresetRegistry
from beastforge.pipeline import build_mesh, preset_documents
from beastforge.rig.skeleton import BuiltSkeleton, build_skeleton
from beastforge.rng import build_digest, run_seed
from beastforge.texture.texforge_adapter import TexforgeLibrary, check_materials
from beastforge.validation.budgets import check_budgets
from beastforge.validation.clips import check_clips
from beastforge.validation.closure import check_closure
from beastforge.validation.common import check_identifier, duplicates, finding
from beastforge.validation.determinism import check_manifest, check_recipe_determinism
from beastforge.validation.hooks import check_hooks
from beastforge.validation.parts import check_geometry_present, check_parts
from beastforge.validation.skeleton import check_skeleton
from beastforge.validation.skin import check_skin
from beastforge.validation.surfaces import check_surfaces


class ValidationFailed(BeastforgeError):
    """A command refused to proceed because the gate found errors."""

    exit_code = 3

    def __init__(self, findings: list[ValidationFinding]) -> None:
        first = findings[0]
        super().__init__(
            first.code,
            first.message,
            location=first.location.model_dump(),
            expected=first.expected,
            actual=first.actual,
            remedy=first.remedy,
            suggestion=first.suggestion,
        )
        self.findings = findings


def check_recipe_metadata(
    recipe: Recipe, *, recipe_label: str, file_stem: str | None
) -> list[ValidationFinding]:
    """Check catalog identity and declared parameters."""
    findings: list[ValidationFinding] = []
    identifier = check_identifier(recipe.meta.name, recipe=recipe_label, path="meta.name")
    if identifier is not None:
        findings.append(identifier)
    if file_stem is not None and recipe.meta.name != file_stem:
        findings.append(
            finding(
                "recipe-name-invalid",
                f"meta.name {recipe.meta.name!r} does not match the file stem {file_stem!r}.",
                recipe=recipe_label,
                path="meta.name",
                expected=file_stem,
                actual=recipe.meta.name,
                remedy="Rename the file or set meta.name to the file stem.",
            )
        )
    if not recipe.meta.description.strip():
        findings.append(
            finding(
                "recipe-name-invalid",
                "meta.description must not be empty.",
                recipe=recipe_label,
                path="meta.description",
                expected="a one-line description",
                actual=recipe.meta.description,
                remedy="Add a short catalog description.",
            )
        )
    if duplicates([tag.lower() for tag in recipe.meta.tags]):
        findings.append(
            finding(
                "duplicate-name",
                "meta.tags contains duplicate values.",
                recipe=recipe_label,
                path="meta.tags",
                expected="unique lowercase tags",
                actual=recipe.meta.tags,
                remedy="Remove the duplicate tag.",
            )
        )
    for tag in recipe.meta.tags:
        if tag != tag.lower() or not tag.strip():
            findings.append(
                finding(
                    "identifier-invalid",
                    f"Tag {tag!r} must be a non-empty lowercase token.",
                    recipe=recipe_label,
                    path="meta.tags",
                    expected="lowercase token",
                    actual=tag,
                    remedy="Lowercase the tag and remove empty entries.",
                )
            )
    seen_params: set[str] = set()
    for param in recipe.params:
        identifier = check_identifier(param.name, recipe=recipe_label, path=f"params[{param.name}]")
        if identifier is not None:
            findings.append(identifier)
        if param.name in seen_params:
            findings.append(
                finding(
                    "duplicate-name",
                    f"Parameter {param.name!r} is declared more than once.",
                    recipe=recipe_label,
                    path=f"params[{param.name}]",
                    expected="unique parameter names",
                    actual=param.name,
                    remedy="Rename one of the duplicate parameters.",
                )
            )
        seen_params.add(param.name)
        if param.type == "enum" and not param.values:
            findings.append(
                finding(
                    "recipe-param-type",
                    f"Enum parameter {param.name!r} has no values.",
                    recipe=recipe_label,
                    path=f"params[{param.name}].values",
                    expected="a closed value list",
                    actual=[],
                    remedy="Add values: [...] to the enum parameter.",
                )
            )
        if param.min is not None and param.max is not None and param.min > param.max:
            findings.append(
                finding(
                    "recipe-param-range",
                    f"Parameter {param.name!r} has min greater than max.",
                    recipe=recipe_label,
                    path=f"params[{param.name}]",
                    expected="min <= max",
                    actual={"min": param.min, "max": param.max},
                    remedy="Swap or correct the limits.",
                )
            )
    if recipe.budgets.vertices < 1 or recipe.budgets.bones < 1 or recipe.budgets.triangles < 1:
        findings.append(
            finding(
                "recipe-param-range",
                "Budget ceilings must be positive.",
                recipe=recipe_label,
                path="budgets",
                expected="vertices, bones, triangles >= 1",
                actual=recipe.budgets.model_dump(),
                remedy="Set positive budget values.",
            )
        )
    return findings


def _registry(settings: Settings | None) -> PresetRegistry:
    """Resolve the preset library for a gate run, tolerating a missing library."""
    try:
        root = find_library_root(settings or Settings())
    except BeastforgeError:
        return PresetRegistry(None)
    return PresetRegistry.from_library_root(root)


def run_gate(
    recipe: Recipe,
    *,
    recipe_label: str,
    file_stem: str | None = None,
    document: dict[str, Any] | None = None,
    settings: Settings | None = None,
    overrides: dict[str, Any] | None = None,
    skeleton: BuiltSkeleton | None = None,
    mesh: Mesh | None = None,
    manifest: Manifest | dict[str, Any] | None = None,
    texforge_root: Path | None = None,
    resolved_parts: list[ResolvedPart] | None = None,
) -> list[ValidationFinding]:
    """Run the full gate and return findings in documented group order."""
    findings: list[ValidationFinding] = []
    findings.extend(check_recipe_metadata(recipe, recipe_label=recipe_label, file_stem=file_stem))
    findings.extend(check_geometry_present(recipe, recipe_label=recipe_label))

    resolution = resolve_params(recipe, overrides, recipe_label=recipe_label, strict=False)
    findings.extend(resolution.findings)

    registry = _registry(settings)
    if resolved_parts is None:
        parts_resolution = check_parts(recipe, registry, recipe_label=recipe_label)
        findings.extend(parts_resolution.findings)
        resolved_parts = parts_resolution.parts

    skeleton_findings = check_skeleton(recipe, recipe_label=recipe_label)
    findings.extend(skeleton_findings)
    if skeleton is None and not skeleton_findings:
        try:
            skeleton = build_skeleton(recipe.skeleton)
        except BeastforgeError as exc:
            findings.append(
                finding(
                    exc.code,
                    exc.message,
                    recipe=recipe_label,
                    path=exc.location.get("path", "skeleton"),
                    expected=exc.expected,
                    actual=exc.actual,
                    remedy=exc.remedy,
                )
            )

    surface_findings = check_surfaces(recipe, recipe_label=recipe_label, parts=resolved_parts)
    findings.extend(surface_findings)

    payload = document if document is not None else recipe.model_dump(mode="json")
    if mesh is None and skeleton is not None:
        try:
            digest = build_digest(payload, preset_documents(resolved_parts))
            seed = run_seed(digest, resolution.values)
            mesh = build_mesh(recipe, skeleton, seed, resolved_parts=resolved_parts)
        except BeastforgeError as exc:
            findings.append(
                finding(
                    exc.code,
                    exc.message,
                    recipe=recipe_label,
                    path=exc.location.get("path", "surfaces"),
                    expected=exc.expected,
                    actual=exc.actual,
                    remedy=exc.remedy,
                )
            )
        except Exception as exc:  # noqa: BLE001 - construction must not crash the gate
            findings.append(
                finding(
                    "surface-empty",
                    f"Surface construction failed: {exc}",
                    recipe=recipe_label,
                    path="surfaces",
                    expected="constructible sweep surfaces",
                    actual=str(exc),
                    remedy="Reduce rings/segments or fix the surface bone list.",
                )
            )

    if mesh is not None and skeleton is not None:
        findings.extend(
            check_skin(
                recipe,
                mesh,
                skeleton,
                recipe_label=recipe_label,
                parts=resolved_parts,
            )
        )
        findings.extend(
            check_closure(
                mesh,
                recipe_label=recipe_label,
                part_names={part.name for part in resolved_parts or []},
            )
        )

    findings.extend(
        check_clips(recipe, recipe_label=recipe_label, max_ticks=recipe.budgets.max_clip_ticks)
    )
    findings.extend(check_hooks(recipe, recipe_label=recipe_label))

    library = TexforgeLibrary(texforge_root)
    findings.extend(
        check_materials(recipe, library, recipe_label=recipe_label, parts=resolved_parts)
    )

    if mesh is not None and skeleton is not None:
        findings.extend(check_budgets(recipe, skeleton, mesh, recipe_label=recipe_label))

    findings.extend(check_recipe_determinism(recipe, recipe_label=recipe_label))
    if manifest is not None:
        findings.extend(
            check_manifest(
                manifest,
                recipe=recipe,
                skeleton_names=set(skeleton.names) if skeleton else None,
                recipe_label=recipe_label,
                parts=resolved_parts,
            )
        )
    return findings


def error_findings(findings: list[ValidationFinding]) -> list[ValidationFinding]:
    """Return only error-severity findings."""
    return [item for item in findings if item.severity == "error"]
