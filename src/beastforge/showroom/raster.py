"""A small deterministic software rasterizer for the showroom (research D12).

Orthographic cameras, a z-buffer, one fixed key light plus ambient, and
nearest-neighbour texture sampling. It is deliberately CPU-only: no GPU, EGL, or
display server is required, which keeps CI and offline generation reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from beastforge.export.gltf import TextureImage
from beastforge.geometry.mesh import Mesh
from beastforge.model.recipe import Recipe
from beastforge.rig.skeleton import BuiltSkeleton, quat_from_axis_angle, quat_to_matrix

FRAME_SIZE = 512
LIGHT_DIRECTION = np.array([-0.35, 0.85, 0.45], dtype=np.float64)
LIGHT_DIRECTION = LIGHT_DIRECTION / np.linalg.norm(LIGHT_DIRECTION)
AMBIENT = 0.35
DIFFUSE = 0.65


@dataclass(frozen=True)
class ViewSpec:
    """One fixed turntable camera direction."""

    name: str
    direction: tuple[float, float, float]


VIEWS: tuple[ViewSpec, ...] = (
    ViewSpec("front", (0.0, 0.0, -1.0)),
    ViewSpec("three-quarter", (-1.0, 0.35, -1.0)),
    ViewSpec("side", (-1.0, 0.0, 0.0)),
    ViewSpec("rear", (0.0, 0.0, 1.0)),
)


def _material_color(name: str) -> np.ndarray:
    digest = __import__("hashlib").sha256(name.encode("utf-8")).digest()
    base = np.array([digest[0], digest[1], digest[2]], dtype=np.float64) / 255.0
    return 0.25 + 0.6 * base


def _decode_texture(texture: TextureImage | None) -> np.ndarray | None:
    if texture is None:
        return None
    image = Image.open(BytesIO(texture.png)).convert("RGB")
    return np.asarray(image, dtype=np.float64) / 255.0


@dataclass
class RenderScene:
    """Prepared mesh/material data shared by every frame of one creature."""

    positions: np.ndarray
    uv: np.ndarray
    indices: np.ndarray
    triangle_material: np.ndarray
    triangle_normals: np.ndarray
    material_names: list[str]
    material_colors: np.ndarray
    texture_arrays: list[np.ndarray | None]
    center: np.ndarray
    scale: float
    up: np.ndarray

    @classmethod
    def build(
        cls,
        *,
        mesh: Mesh,
        recipe: Recipe,
        textures: list[TextureImage],
    ) -> RenderScene:
        """Prepare materials, normals, and a fixed orthographic scale."""
        material_names = [material.name for material in recipe.materials]
        index_by_name = {name: index for index, name in enumerate(material_names)}
        texture_by_name = {texture.material: texture for texture in textures}
        if material_names:
            material_colors = np.asarray([_material_color(name) for name in material_names])
        else:
            material_colors = np.asarray([[0.6, 0.6, 0.6]])
        texture_arrays = [_decode_texture(texture_by_name.get(name)) for name in material_names]

        triangle_material = np.full(mesh.triangle_count, -1, dtype=np.int32)
        for surface_range, surface in zip(mesh.surfaces, recipe.surfaces, strict=False):
            if surface.material in index_by_name:
                start = surface_range.index_offset
                end = start + surface_range.index_count
                triangle_material[start:end] = index_by_name[surface.material]

        triangles = mesh.positions[mesh.indices]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        lengths[lengths == 0.0] = 1.0
        normals = normals / lengths[:, None]

        bounds_min, bounds_max = mesh.bounds()
        center = (bounds_min + bounds_max) * 0.5
        radius = float(np.linalg.norm(bounds_max - center))
        radius = max(radius, 1e-6)
        scale = (FRAME_SIZE * 0.5) / (radius * 1.12)
        return cls(
            positions=mesh.positions,
            uv=mesh.uv,
            indices=mesh.indices,
            triangle_material=triangle_material,
            triangle_normals=normals,
            material_names=material_names,
            material_colors=material_colors,
            texture_arrays=texture_arrays,
            center=center,
            scale=scale,
            up=np.array([0.0, 1.0, 0.0], dtype=np.float64),
        )


def _project(
    scene: RenderScene, direction: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    direction = direction / np.linalg.norm(direction)
    forward = -direction
    right = np.cross(scene.up, forward)
    right_norm = np.linalg.norm(right)
    right = right / right_norm if right_norm > 1e-12 else np.array([1.0, 0.0, 0.0])
    camera_up = np.cross(forward, right)
    relative = scene.positions - scene.center
    x = relative @ right * scene.scale + FRAME_SIZE * 0.5
    y = -(relative @ camera_up) * scene.scale + FRAME_SIZE * 0.5
    depth = relative @ direction
    return x, y, depth


def render_frame(
    scene: RenderScene,
    direction: np.ndarray,
    *,
    positions: np.ndarray | None = None,
) -> np.ndarray:
    """Rasterize one RGBA frame; background pixels have alpha 0."""
    if positions is not None:
        scene = RenderScene(
            positions=positions,
            uv=scene.uv,
            indices=scene.indices,
            triangle_material=scene.triangle_material,
            triangle_normals=_face_normals(positions, scene.indices),
            material_names=scene.material_names,
            material_colors=scene.material_colors,
            texture_arrays=scene.texture_arrays,
            center=scene.center,
            scale=scene.scale,
            up=scene.up,
        )
    x, y, depth = _project(scene, direction)
    color = np.zeros((FRAME_SIZE, FRAME_SIZE, 4), dtype=np.uint8)
    color[:, :, :3] = np.array([18, 22, 30], dtype=np.uint8)
    zbuffer = np.full((FRAME_SIZE, FRAME_SIZE), -np.inf, dtype=np.float64)

    indices = scene.indices
    for triangle in range(indices.shape[0]):
        i0, i1, i2 = int(indices[triangle, 0]), int(indices[triangle, 1]), int(indices[triangle, 2])
        x0, x1, x2 = float(x[i0]), float(x[i1]), float(x[i2])
        y0, y1, y2 = float(y[i0]), float(y[i1]), float(y[i2])
        min_x = max(0, int(np.floor(min(x0, x1, x2))))
        max_x = min(FRAME_SIZE - 1, int(np.ceil(max(x0, x1, x2))))
        min_y = max(0, int(np.floor(min(y0, y1, y2))))
        max_y = min(FRAME_SIZE - 1, int(np.ceil(max(y0, y1, y2))))
        if min_x > max_x or min_y > max_y:
            continue
        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) < 1e-12:
            continue
        xs = np.arange(min_x, max_x + 1, dtype=np.float64) + 0.5
        ys = np.arange(min_y, max_y + 1, dtype=np.float64) + 0.5
        grid_x, grid_y = np.meshgrid(xs, ys)
        w0 = ((y1 - y2) * (grid_x - x2) + (x2 - x1) * (grid_y - y2)) / denominator
        w1 = ((y2 - y0) * (grid_x - x2) + (x0 - x2) * (grid_y - y2)) / denominator
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not np.any(inside):
            continue
        triangle_depth = w0 * depth[i0] + w1 * depth[i1] + w2 * depth[i2]
        region = zbuffer[min_y : max_y + 1, min_x : max_x + 1]
        update = inside & (triangle_depth > region)
        if not np.any(update):
            continue
        material = int(scene.triangle_material[triangle])
        shade = AMBIENT + DIFFUSE * abs(float(scene.triangle_normals[triangle] @ LIGHT_DIRECTION))
        if material >= 0:
            texture = scene.texture_arrays[material]
            if texture is not None:
                u = w0 * scene.uv[i0, 0] + w1 * scene.uv[i1, 0] + w2 * scene.uv[i2, 0]
                v = w0 * scene.uv[i0, 1] + w1 * scene.uv[i1, 1] + w2 * scene.uv[i2, 1]
                height, width = texture.shape[:2]
                tex_x = np.clip(((u % 1.0) * (width - 1)).astype(np.int32), 0, width - 1)
                tex_y = np.clip(((v % 1.0) * (height - 1)).astype(np.int32), 0, height - 1)
                base = texture[tex_y, tex_x]
            else:
                base = np.broadcast_to(
                    scene.material_colors[material], (grid_x.shape[0], grid_x.shape[1], 3)
                )
        else:
            base = np.broadcast_to(np.array([0.6, 0.6, 0.6]), (grid_x.shape[0], grid_x.shape[1], 3))
        lit = np.clip(base * shade, 0.0, 1.0)
        region[update] = triangle_depth[update]
        target = color[min_y : max_y + 1, min_x : max_x + 1, :3]
        target[update] = (lit[update] * 255.0).astype(np.uint8)
        alpha = color[min_y : max_y + 1, min_x : max_x + 1, 3]
        alpha[update] = 255
    return color


def _face_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    triangles = positions[indices]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths == 0.0] = 1.0
    return normals / lengths[:, None]


def choose_test_joint(recipe: Recipe, skeleton: BuiltSkeleton) -> str:
    """Pick a deterministic joint for the extreme-bend frame."""
    for chain in recipe.skeleton.chains:
        if len(chain.bones) >= 2:
            return chain.bones[1]
    candidates = sorted(
        skeleton.names, key=lambda name: (-len(skeleton.children.get(name, [])), name)
    )
    return candidates[0] if candidates else skeleton.node_order[0]


def pose_extreme_bend(
    recipe: Recipe,
    skeleton: BuiltSkeleton,
    mesh: Mesh,
    *,
    angle: float = np.pi * 0.5,
) -> np.ndarray:
    """Skin the mesh with one joint rotated ±90° to expose shearing."""
    joint = choose_test_joint(recipe, skeleton)
    delta = np.eye(4, dtype=np.float64)
    delta[:3, :3] = quat_to_matrix(quat_from_axis_angle(np.array([1.0, 0.0, 0.0]), angle))
    world: dict[str, np.ndarray] = {}
    for name in skeleton.node_order:
        local = skeleton.local_matrices[name].copy()
        if name == joint:
            local = local @ delta
        parent = skeleton.parent_of(name)
        world[name] = local if parent is None else world[parent] @ local
    skin: dict[str, np.ndarray] = {
        name: world[name] @ skeleton.inverse_bind[name] for name in skeleton.node_order
    }
    matrices = np.asarray([skin[name] for name in skeleton.node_order], dtype=np.float64)
    homogeneous = np.concatenate(
        [mesh.positions, np.ones((mesh.vertex_count, 1), dtype=np.float64)], axis=1
    )
    result = np.zeros((mesh.vertex_count, 3), dtype=np.float64)
    for column in range(4):
        weights = mesh.weights[:, column]
        mask = weights > 0.0
        if not np.any(mask):
            continue
        joint_indices = mesh.joints[mask, column]
        transformed = np.einsum("nij,nj->ni", matrices[joint_indices], homogeneous[mask])[:, :3]
        result[mask] += weights[mask, None] * transformed
    return result


def encode_png(rgba: np.ndarray) -> bytes:
    """Encode an RGBA frame to PNG with pinned, empty metadata."""
    from io import BytesIO

    from PIL import PngImagePlugin

    buffer = BytesIO()
    image = Image.fromarray(rgba, mode="RGBA")
    image.save(buffer, format="PNG", pnginfo=PngImagePlugin.PngInfo())
    return buffer.getvalue()
