"""Skeleton world transforms and inverse bind matrices."""

from __future__ import annotations

import numpy as np

from beastforge.model.loader import load_recipe
from beastforge.rig.skeleton import build_skeleton, quat_normalize


def test_inverse_bind_is_the_inverse_of_rest_world(repo_root) -> None:
    recipe, _ = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    skeleton = build_skeleton(recipe.skeleton)
    identity = np.eye(4)
    for name in skeleton.names:
        assert np.allclose(skeleton.inverse_bind[name] @ skeleton.world_matrices[name], identity)
    assert skeleton.node_order[0] == recipe.skeleton.root


def test_chain_bones_have_positive_length(repo_root) -> None:
    recipe, _ = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    skeleton = build_skeleton(recipe.skeleton)
    for chain in recipe.skeleton.chains:
        for bone in chain.bones:
            assert skeleton.bone_length(bone) > 0.0


def test_quaternions_are_normalized(repo_root) -> None:
    recipe, _ = load_recipe(repo_root / "library/quadruped/ridge-stalker.yaml")
    skeleton = build_skeleton(recipe.skeleton)
    for name in skeleton.names:
        assert (
            abs(float(np.linalg.norm(quat_normalize(skeleton.world_rotations[name]))) - 1.0) < 1e-9
        )
