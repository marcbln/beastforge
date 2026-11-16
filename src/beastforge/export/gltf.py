"""Deterministic glTF 2.0 binary writer (research D3, ADR 261114-2).

Emission order is fixed: per-surface attributes and indices, inverse bind
matrices, animation samplers in reserved-clip order, and embedded PNG
bufferViews. JSON is canonical (sorted keys, ASCII, compact, no -0.0), so the
bytes are a pure function of the inputs.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

import numpy as np

from beastforge.anim.bake import BakedClip
from beastforge.geometry.mesh import Mesh
from beastforge.model.findings import CORE_CLIPS
from beastforge.model.recipe import Material, Recipe
from beastforge.rig.skeleton import BuiltSkeleton
from beastforge.utils.canonical import canonical_json

MAGIC = 0x46546C67
VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT = 5126
UNSIGNED_SHORT = 5123
UNSIGNED_INT = 5125
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


@dataclass
class TextureImage:
    """One rendered texforge texture destined for the GLB."""

    material: str
    recipe: str
    params: dict[str, Any]
    size: str
    width: int
    height: int
    sha256: str
    png: bytes


class GLTFBuilder:
    """Accumulate accessors, bufferViews, and the binary chunk."""

    def __init__(self) -> None:
        self.binary = bytearray()
        self.buffer_views: list[dict[str, Any]] = []
        self.accessors: list[dict[str, Any]] = []

    def _align(self) -> None:
        padding = (-len(self.binary)) % 4
        if padding:
            self.binary.extend(b"\x00" * padding)

    def add_buffer_view(self, data: bytes, *, target: int | None = None) -> int:
        self._align()
        offset = len(self.binary)
        self.binary.extend(data)
        view: dict[str, Any] = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(data),
        }
        if target is not None:
            view["target"] = target
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1

    def add_accessor(
        self,
        array: np.ndarray,
        component_type: int,
        type_name: str,
        *,
        target: int | None = None,
        bounds: bool = False,
        normalized: bool = False,
    ) -> int:
        data = np.ascontiguousarray(array)
        view = self.add_buffer_view(data.tobytes(order="C"), target=target)
        accessor: dict[str, Any] = {
            "bufferView": view,
            "componentType": component_type,
            "count": int(data.shape[0]),
            "type": type_name,
        }
        if normalized:
            accessor["normalized"] = True
        if bounds:
            if data.ndim == 1:
                accessor["min"] = [float(data.min())]
                accessor["max"] = [float(data.max())]
            else:
                accessor["min"] = [float(value) for value in data.min(axis=0)]
                accessor["max"] = [float(value) for value in data.max(axis=0)]
        self.accessors.append(accessor)
        return len(self.accessors) - 1


def _ordered_clips(clips: list[BakedClip]) -> list[BakedClip]:
    by_name = {clip.name: clip for clip in clips}
    ordered = [by_name[name] for name in CORE_CLIPS if name in by_name]
    ordered.extend(
        sorted((clip for clip in clips if clip.name not in CORE_CLIPS), key=lambda c: c.name)
    )
    return ordered


def _material_json(material: Material, texture_index: int) -> dict[str, Any]:
    # Invariant: never emit doubleSided. Backface culling proves closed geometry;
    # a two-sided material would hide an open part (FR-003, SC-008).
    return {
        "name": material.name,
        "pbrMetallicRoughness": {
            "baseColorTexture": {"index": texture_index},
            "metallicFactor": float(material.metallic),
            "roughnessFactor": float(material.roughness),
        },
    }


def _column_major(matrix: np.ndarray) -> np.ndarray:
    return np.asarray(matrix, dtype=np.float64).T.reshape(-1)


def build_glb(
    *,
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    mesh: Mesh,
    clips: list[BakedClip],
    textures: list[TextureImage],
    tool_version: str,
) -> bytes:
    """Assemble one deterministic GLB from the built artifacts."""
    builder = GLTFBuilder()
    node_index = {name: index for index, name in enumerate(skeleton.node_order)}

    # --- images, samplers, textures, materials -----------------------------
    images: list[dict[str, Any]] = []
    texture_json: list[dict[str, Any]] = []
    materials_json: list[dict[str, Any]] = []
    material_index: dict[str, int] = {}
    texture_by_material = {texture.material: texture for texture in textures}
    for material in recipe.materials:
        texture = texture_by_material.get(material.name)
        if texture is None:
            continue
        view = builder.add_buffer_view(texture.png)
        images.append({"bufferView": view, "mimeType": "image/png"})
        texture_json.append({"sampler": 0, "source": len(images) - 1})
        material_index[material.name] = len(materials_json)
        materials_json.append(_material_json(material, len(texture_json) - 1))
    samplers = (
        [
            {
                "magFilter": 9729,
                "minFilter": 9987,
                "wrapS": 10497,
                "wrapT": 10497,
            }
        ]
        if texture_json
        else []
    )

    # --- mesh primitives ----------------------------------------------------
    primitives: list[dict[str, Any]] = []
    for surface_range in mesh.surfaces:
        vertex_slice = slice(
            surface_range.vertex_offset,
            surface_range.vertex_offset + surface_range.vertex_count,
        )
        index_end = surface_range.index_offset + surface_range.index_count
        indices = mesh.indices[surface_range.index_offset : index_end].reshape(-1)
        indices = (indices - surface_range.vertex_offset).astype(np.uint32)
        position_accessor = builder.add_accessor(
            mesh.positions[vertex_slice].astype(np.float32),
            FLOAT,
            "VEC3",
            target=ARRAY_BUFFER,
            bounds=True,
        )
        normal_accessor = builder.add_accessor(
            mesh.normals[vertex_slice].astype(np.float32), FLOAT, "VEC3", target=ARRAY_BUFFER
        )
        uv_accessor = builder.add_accessor(
            mesh.uv[vertex_slice].astype(np.float32), FLOAT, "VEC2", target=ARRAY_BUFFER
        )
        joints_accessor = builder.add_accessor(
            mesh.joints[vertex_slice].astype(np.uint16), UNSIGNED_SHORT, "VEC4", target=ARRAY_BUFFER
        )
        weights_accessor = builder.add_accessor(
            mesh.weights[vertex_slice].astype(np.float32), FLOAT, "VEC4", target=ARRAY_BUFFER
        )
        index_accessor = builder.add_accessor(
            indices, UNSIGNED_INT, "SCALAR", target=ELEMENT_ARRAY_BUFFER
        )
        primitive: dict[str, Any] = {
            "attributes": {
                "POSITION": position_accessor,
                "NORMAL": normal_accessor,
                "TEXCOORD_0": uv_accessor,
                "JOINTS_0": joints_accessor,
                "WEIGHTS_0": weights_accessor,
            },
            "indices": index_accessor,
            "mode": 4,
        }
        if surface_range.material in material_index:
            primitive["material"] = material_index[surface_range.material]
        primitives.append(primitive)

    inverse_bind = np.asarray(
        [_column_major(skeleton.inverse_bind[name]) for name in skeleton.node_order],
        dtype=np.float32,
    )
    inverse_bind_accessor = builder.add_accessor(inverse_bind, FLOAT, "MAT4")

    # --- nodes (root first, then declaration order, then mesh) --------------
    nodes: list[dict[str, Any]] = []
    for name in skeleton.node_order:
        rest = skeleton.local_transforms[name]
        node: dict[str, Any] = {
            "name": name,
            "translation": [float(value) for value in rest.translation],
            "rotation": [float(value) for value in rest.rotation],
            "scale": [float(value) for value in rest.scale],
        }
        children = [node_index[child] for child in skeleton.children[name]]
        if children:
            node["children"] = children
        nodes.append(node)
    mesh_node_index = len(nodes)
    nodes.append({"name": f"{recipe.meta.name}-mesh", "mesh": 0, "skin": 0})

    # --- animations ---------------------------------------------------------
    animations: list[dict[str, Any]] = []
    for clip in _ordered_clips(clips):
        channels: list[dict[str, Any]] = []
        samplers_json: list[dict[str, Any]] = []
        for track in clip.tracks:
            time_accessor = builder.add_accessor(track.times.astype(np.float32), FLOAT, "SCALAR")
            for path, values, type_name in (
                ("translation", track.translations, "VEC3"),
                ("rotation", track.rotations, "VEC4"),
                ("scale", track.scales, "VEC3"),
            ):
                output_accessor = builder.add_accessor(values.astype(np.float32), FLOAT, type_name)
                sampler_index = len(samplers_json)
                samplers_json.append(
                    {
                        "input": time_accessor,
                        "output": output_accessor,
                        "interpolation": "LINEAR",
                    }
                )
                channels.append(
                    {
                        "sampler": sampler_index,
                        "target": {"node": node_index[track.name], "path": path},
                    }
                )
        animations.append({"name": clip.name, "channels": channels, "samplers": samplers_json})

    # --- assemble JSON ------------------------------------------------------
    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": f"beastforge {tool_version}"},
        "scene": 0,
        "scenes": [{"nodes": [node_index[skeleton.node_order[0]], mesh_node_index]}],
        "nodes": nodes,
        "meshes": [{"name": recipe.meta.name, "primitives": primitives}],
        "skins": [
            {
                "name": f"{recipe.meta.name}-skin",
                "inverseBindMatrices": inverse_bind_accessor,
                "skeleton": node_index[skeleton.node_order[0]],
                "joints": [node_index[name] for name in skeleton.node_order],
            }
        ],
        "accessors": builder.accessors,
        "bufferViews": builder.buffer_views,
        "buffers": [{"byteLength": len(builder.binary)}],
    }
    if material_json := materials_json:
        document["materials"] = material_json
    if texture_json:
        document["textures"] = texture_json
        document["images"] = images
        document["samplers"] = samplers
    if animations:
        document["animations"] = animations

    json_bytes = canonical_json(document, trailing_newline=False).encode("utf-8")
    json_bytes += b" " * ((-len(json_bytes)) % 4)
    bin_bytes = bytes(builder.binary)
    bin_bytes += b"\x00" * ((-len(bin_bytes)) % 4)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    return b"".join(
        [
            struct.pack("<III", MAGIC, VERSION, total_length),
            struct.pack("<II", len(json_bytes), JSON_CHUNK),
            json_bytes,
            struct.pack("<II", len(bin_bytes), BIN_CHUNK),
            bin_bytes,
        ]
    )
