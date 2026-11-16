"""Pinned gameplay facts for the five shipped creatures (SC-003).

Only stable facts are compared: joints, clips, events, sockets, volumes, phases,
materials, units, and axes. Bytes, schemaVersion, and clip ``source`` are not
gameplay facts and are covered by their own tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from beastforge.model.loader import load_recipe
from beastforge.model.recipe import Recipe
from beastforge.pipeline import prepare

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "tests/golden/gameplay_facts.json"
CREATURES = {
    "ash-crowned-tyrant": ROOT / "library/boss/ash-crowned-tyrant.yaml",
    "ridge-stalker": ROOT / "library/quadruped/ridge-stalker.yaml",
    "chitter-mite": ROOT / "library/swarm/chitter-mite.yaml",
    "giraffe": ROOT / "library/quadruped/giraffe.yaml",
    "elephant": ROOT / "library/quadruped/elephant.yaml",
}


def _event_time(event) -> float:
    return event.ticks / 60.0 if event.ticks is not None else float(event.time or 0.0)


def facts_for(recipe: Recipe, document: dict) -> dict:
    built = prepare(
        recipe,
        document=document,
        recipe_path=recipe.meta.name,
        tool_version="0.1.0",
    )
    return {
        "units": recipe.meta.units,
        "upAxis": recipe.meta.orientation.up,
        "forwardAxis": recipe.meta.orientation.forward,
        "joints": [
            {"name": name, "parent": built.skeleton.parent_of(name)}
            for name in built.skeleton.node_order
        ],
        "clips": [
            {
                "name": clip.name,
                "duration": clip.duration,
                "loop": clip.loop,
                "generator": clip.generator,
            }
            for clip in built.clips
        ],
        "events": [
            {"clip": clip.name, "time": _event_time(event), "name": event.name}
            for clip in recipe.clips
            for event in clip.events
        ],
        "sockets": [
            {"name": socket.name, "target": socket.bone, "offset": socket.offset}
            for socket in recipe.sockets
        ],
        "volumes": [
            {
                "name": volume.name,
                "role": volume.role,
                "center": volume.center,
                "extents": volume.extents,
                "bone": volume.bone,
            }
            for volume in recipe.volumes
        ],
        "phases": [
            {"name": phase.name, "threshold": phase.threshold} for phase in recipe.phases
        ],
        "materials": [
            {
                "name": material.name,
                "slot": material.slot,
                "texture": material.texture,
                "params": material.params,
                "size": material.size,
                "metallic": material.metallic,
                "roughness": material.roughness,
            }
            for material in recipe.materials
        ],
    }


def collect_facts() -> dict[str, dict]:
    facts: dict[str, dict] = {}
    for name, path in CREATURES.items():
        recipe, document = load_recipe(path)
        facts[name] = facts_for(recipe, document)
    return facts


def test_gameplay_facts_match_pinned_snapshot() -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert collect_facts() == expected
