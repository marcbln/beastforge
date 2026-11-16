"""Seeded defect corpus: every curated defect gets its own stable code (SC-004)."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import yaml

from beastforge.geometry.mesh import Mesh
from beastforge.model.loader import RecipeParseError, load_yaml_document, parse_recipe
from beastforge.model.manifest import Manifest
from beastforge.pipeline import prepare
from beastforge.validation.determinism import check_manifest
from beastforge.validation.gate import run_gate
from beastforge.validation.skin import check_skin

ROOT = Path(__file__).resolve().parents[2]
TEXFORGE = ROOT.parent / "texforge" / "library"
QUADRUPED = yaml.safe_load((ROOT / "library/quadruped/ridge-stalker.yaml").read_text())
BOSS = yaml.safe_load((ROOT / "library/boss/ash-crowned-tyrant.yaml").read_text())


def _codes(document: dict, *, file_stem: str | None = None) -> list[str]:
    recipe = parse_recipe(document, recipe_label="broken.yaml")
    findings = run_gate(
        recipe,
        recipe_label="broken.yaml",
        file_stem=file_stem,
        document=document,
        texforge_root=TEXFORGE,
    )
    return [finding.code for finding in findings]


def _mutate(base: dict, change) -> dict:
    document = copy.deepcopy(base)
    change(document)
    return document


def _bone(document: dict, name: str) -> dict:
    return next(bone for bone in document["skeleton"]["bones"] if bone["name"] == name)


def _clip(document: dict, name: str) -> dict:
    return next(clip for clip in document["clips"] if clip["name"] == name)


def test_missing_core_clip() -> None:
    document = _mutate(
        QUADRUPED,
        lambda d: d.__setitem__("clips", [c for c in d["clips"] if c["name"] != "attack"]),
    )
    assert "clip-missing-core" in _codes(document)


def test_duplicate_bone() -> None:
    document = _mutate(QUADRUPED, lambda d: _bone(d, "spine-02").__setitem__("name", "spine-01"))
    assert "skeleton-duplicate-bone" in _codes(document)


def test_bone_cycle() -> None:
    document = _mutate(QUADRUPED, lambda d: _bone(d, "upper-fl").__setitem__("parent", "foot-fl"))
    assert "skeleton-cycle" in _codes(document)


def test_parent_missing() -> None:
    document = _mutate(
        QUADRUPED, lambda d: _bone(d, "spine-02").__setitem__("parent", "missing-bone")
    )
    assert "skeleton-parent-missing" in _codes(document)


def test_degenerate_and_inverted_transforms() -> None:
    document = _mutate(
        QUADRUPED, lambda d: _bone(d, "spine-02")["rest"].__setitem__("rotation", [0, 0, 0, 0])
    )
    assert "skeleton-degenerate-transform" in _codes(document)
    document = _mutate(
        QUADRUPED, lambda d: _bone(d, "spine-02")["rest"].__setitem__("scale", [-1, 1, 1])
    )
    assert "skeleton-inverted-transform" in _codes(document)


def test_zero_length_chain_bone() -> None:
    document = _mutate(
        QUADRUPED, lambda d: _bone(d, "upper-fl")["rest"].__setitem__("translation", [0, 0, 0])
    )
    assert "skeleton-zero-length-bone" in _codes(document)


def test_chain_invalid_and_duplicate() -> None:
    def break_chain(d: dict) -> None:
        d["skeleton"]["chains"][0]["bones"] = ["foot-fl", "lower-fl", "upper-fl"]

    assert "chain-invalid" in _codes(_mutate(QUADRUPED, break_chain))

    def duplicate_chain(d: dict) -> None:
        d["skeleton"]["chains"][1]["name"] = d["skeleton"]["chains"][0]["name"]

    assert "chain-duplicate" in _codes(_mutate(QUADRUPED, duplicate_chain))


def test_unsupported_surface_mode_and_missing_bone() -> None:
    document = _mutate(QUADRUPED, lambda d: d["surfaces"][0].__setitem__("mode", "metaball"))
    assert "surface-unsupported-mode" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["surfaces"][0].__setitem__("bones", ["missing-bone"]))
    assert "surface-bone-missing" in _codes(document)


def test_surface_empty() -> None:
    document = _mutate(QUADRUPED, lambda d: d["surfaces"][0].__setitem__("rings", 1))
    assert "surface-empty" in _codes(document)


def test_missing_hit_volume_and_boss_phases() -> None:
    document = _mutate(
        QUADRUPED,
        lambda d: d.__setitem__(
            "volumes",
            [{"name": "hull", "role": "collision", "center": [0, 0, 0], "extents": [1, 1, 1]}],
        ),
    )
    assert "volume-missing-hit" in _codes(document)
    document = _mutate(BOSS, lambda d: d.__setitem__("phases", []))
    assert "phase-missing-for-boss" in _codes(document)


def test_dangling_socket_and_volume_bone() -> None:
    document = _mutate(QUADRUPED, lambda d: d["sockets"][0].__setitem__("bone", "missing-bone"))
    assert "socket-target-missing" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["volumes"][0].__setitem__("bone", "missing-bone"))
    assert "manifest-dangling-reference" in _codes(document)


def test_missing_texture_and_invalid_material_params() -> None:
    document = _mutate(
        QUADRUPED, lambda d: d["materials"][0].__setitem__("texture", "does-not-exist")
    )
    assert "material-unresolved" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["materials"][0]["params"].__setitem__("unknown", 1))
    assert "material-param-invalid" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["materials"][0].__setitem__("size", "large"))
    assert "material-size-invalid" in _codes(document)


def test_event_timing_defects() -> None:
    document = _mutate(
        QUADRUPED, lambda d: _clip(d, "attack")["events"][0].__setitem__("ticks", 9999)
    )
    assert "clip-event-out-of-range" in _codes(document)

    def negative_event(d: dict) -> None:
        event = _clip(d, "attack")["events"][0]
        event.pop("ticks", None)
        event["time"] = -1

    document = _mutate(QUADRUPED, negative_event)
    assert "clip-event-negative-time" in _codes(document)


def test_clip_inventory_and_generator_defects() -> None:
    document = _mutate(QUADRUPED, lambda d: d["clips"].append(copy.deepcopy(d["clips"][0])))
    assert "clip-duplicate" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: _clip(d, "idle").__setitem__("generator", "spin"))
    assert "clip-unknown-generator" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: _clip(d, "idle")["params"].__setitem__("unknown", 1))
    assert "clip-param-invalid" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: _clip(d, "idle").__setitem__("duration", 0))
    assert "clip-nonpositive-duration" in _codes(document)

    def over_budget(d: dict) -> None:
        clip = _clip(d, "idle")
        clip.pop("duration", None)
        clip["ticks"] = 9999

    document = _mutate(QUADRUPED, over_budget)
    assert "clip-duration-over-budget" in _codes(document)


def test_duplicate_hook_names() -> None:
    document = _mutate(QUADRUPED, lambda d: d["sockets"].append(copy.deepcopy(d["sockets"][0])))
    assert "socket-duplicate" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["volumes"].append(copy.deepcopy(d["volumes"][0])))
    assert "volume-duplicate" in _codes(document)
    document = _mutate(BOSS, lambda d: d["phases"].append(copy.deepcopy(d["phases"][0])))
    assert "phase-duplicate" in _codes(document)


def test_phase_threshold_and_role() -> None:
    document = _mutate(BOSS, lambda d: d["phases"][0].__setitem__("threshold", 1.5))
    assert "phase-threshold-range" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: d["volumes"][0].__setitem__("role", "door"))
    assert "volume-role-invalid" in _codes(document)


def test_budget_exceeded() -> None:
    document = _mutate(QUADRUPED, lambda d: d["budgets"].__setitem__("vertices", 1))
    assert "budget-exceeded" in _codes(document)


def test_name_rules_and_duplicate_names() -> None:
    document = _mutate(QUADRUPED, lambda d: d["meta"].__setitem__("name", "ridge-stalker"))
    assert "recipe-name-invalid" in _codes(document, file_stem="other-name")
    document = _mutate(
        QUADRUPED, lambda d: d["surfaces"][1].__setitem__("name", d["surfaces"][0]["name"])
    )
    assert "duplicate-name" in _codes(document)
    document = _mutate(QUADRUPED, lambda d: _bone(d, "spine-02").__setitem__("name", "Bad Name"))
    assert "identifier-invalid" in _codes(document)


def test_determinism_hazard() -> None:
    document = _mutate(QUADRUPED, lambda d: d["meta"].__setitem__("units", "cm"))
    assert "determinism-hazard" in _codes(document)


def test_unknown_field_and_executable_content(tmp_path) -> None:
    document = _mutate(QUADRUPED, lambda d: d.__setitem__("mystery", 1))
    with pytest.raises(RecipeParseError) as exc:
        parse_recipe(document, recipe_label="broken.yaml")
    assert exc.value.findings[0].code == "recipe-unknown-field"

    bad = tmp_path / "bad.yaml"
    bad.write_text("!!python/object:os.system 'echo hi'\n")
    with pytest.raises(RecipeParseError) as exc:
        load_yaml_document(bad, recipe_label="bad.yaml")
    assert exc.value.findings[0].code == "recipe-executable-content"


def test_fractional_ticks(tmp_path) -> None:
    document = _mutate(QUADRUPED, lambda d: _clip(d, "idle").__setitem__("ticks", 1.5))
    document["clips"][0].pop("duration", None)
    with pytest.raises(RecipeParseError) as exc:
        parse_recipe(document, recipe_label="broken.yaml")
    assert "clip-fractional-ticks" in [finding.code for finding in exc.value.findings]


@pytest.fixture()
def built():
    recipe, document = None, None
    from beastforge.model.loader import load_recipe

    recipe, document = load_recipe(ROOT / "library/quadruped/ridge-stalker.yaml")
    return prepare(recipe, document=document, recipe_path="ridge-stalker", tool_version="0.1.0")


def _skin_codes(built, mutate) -> list[str]:
    import copy as copy_module

    mesh = copy_module.deepcopy(built.mesh)
    mutate(mesh)
    findings = check_skin(built.recipe, mesh, built.skeleton, recipe_label="broken.yaml")
    return [finding.code for finding in findings]


def test_skin_weight_sum(built) -> None:
    assert "skin-weight-sum" in _skin_codes(
        built, lambda mesh: mesh.weights.__setitem__(0, mesh.weights[0] * 1.2)
    )


def test_skin_zero_weight(built) -> None:
    assert "skin-zero-weight" in _skin_codes(
        built, lambda mesh: mesh.weights.__setitem__(0, np.zeros(4))
    )


def test_skin_too_many_influences(built) -> None:
    def add_fifth(mesh: Mesh) -> None:
        mesh.weights = np.concatenate([mesh.weights, np.zeros((mesh.vertex_count, 1))], axis=1)
        mesh.weights[0] = [0.2, 0.2, 0.2, 0.2, 0.2]
        mesh.joints = np.concatenate(
            [mesh.joints, np.zeros((mesh.vertex_count, 1), dtype=np.uint16)], axis=1
        )

    assert "skin-too-many-influences" in _skin_codes(built, add_fifth)


def test_skin_bind_pose_mismatch(built) -> None:
    def corrupt(mesh: Mesh) -> None:
        built.skeleton.inverse_bind["spine-02"] = np.eye(4)

    try:
        assert "skin-bind-pose-mismatch" in _skin_codes(built, corrupt)
    finally:
        from beastforge.rig.skeleton import build_skeleton

        rebuilt = build_skeleton(built.recipe.skeleton)
        built.skeleton.inverse_bind.update(rebuilt.inverse_bind)


def test_surface_winding_and_degenerate_faces(built) -> None:
    from beastforge.validation.closure import check_closure

    def closure_codes(mutate) -> list[str]:
        import copy as copy_module

        mesh = copy_module.deepcopy(built.mesh)
        mutate(mesh)
        return [
            finding.code
            for finding in check_closure(mesh, recipe_label="broken.yaml")
        ]

    assert "surface-winding-invalid" in closure_codes(
        lambda mesh: mesh.indices.__setitem__(slice(None), mesh.indices[:, [0, 2, 1]])
    )
    assert "surface-degenerate" in closure_codes(
        lambda mesh: mesh.positions.__setitem__(1, mesh.positions[0])
    )


def test_rigid_multi_influence(built) -> None:
    rigid_index = next(
        index for index, surface in enumerate(built.recipe.surfaces) if surface.kind == "rigid-part"
    )
    surface_range = built.mesh.surfaces[rigid_index]
    start = surface_range.vertex_offset

    def corrupt(mesh: Mesh) -> None:
        mesh.weights[start] = [0.5, 0.5, 0.0, 0.0]

    assert "skin-rigid-multi-influence" in _skin_codes(built, corrupt)


def test_manifest_refs_and_version(rendered) -> None:
    assert rendered.manifest is not None
    from beastforge.export.manifest import manifest_json

    payload = manifest_json(rendered.manifest)
    manifest = Manifest.model_validate(payload)
    codes = [
        finding.code
        for finding in check_manifest(manifest, recipe=None, skeleton_names=None, recipe_label="x")
    ]
    assert codes == []

    payload["events"][0]["clip"] = "missing-clip"
    codes = [
        finding.code
        for finding in check_manifest(payload, recipe=None, skeleton_names=None, recipe_label="x")
    ]
    assert "manifest-dangling-reference" in codes

    payload["schemaVersion"] = "2.0"
    codes = [
        finding.code
        for finding in check_manifest(payload, recipe=None, skeleton_names=None, recipe_label="x")
    ]
    assert "manifest-schema-unsupported" in codes
