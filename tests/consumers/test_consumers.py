"""Independent consumer import: trimesh must load the skinned GLB."""

from __future__ import annotations

import json
import struct


def test_trimesh_loads_skinned_glb(rendered) -> None:
    import trimesh

    scene = trimesh.load(rendered.report.outputs.glb.path)
    assert len(scene.geometry) >= 1
    assert any(len(geometry.vertices) > 0 for geometry in scene.geometry.values())


def test_glb_declares_skin_and_animations(rendered) -> None:
    data = rendered.glb
    assert data is not None
    json_length, _ = struct.unpack("<II", data[12:20])
    document = json.loads(data[20 : 20 + json_length].decode("utf-8").rstrip(" "))
    assert document["skins"]
    assert document["animations"]
    assert len(document["skins"][0]["joints"]) == len(document["nodes"]) - 1
