"""Locate the buildless frontend as package data.

Both delivery modes expose the same URLs: ``/assets/<path>`` serves the static
frontend (``styles.css``, ``app.js``, ``lib/...``) and the vendored runtime,
whose URL prefix ``assets/three/`` maps to ``third_party/three/``. The locator
uses :mod:`importlib.resources` so editable and wheel installs behave alike.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib import resources
from importlib.resources.abc import Traversable

PACKAGE = "beastforge.viewer"
STATIC_DIR = "static"
THREE_DIR = "third_party/three"
THREE_PREFIX = "assets/three/"


def static_root() -> Traversable:
    """Return the packaged ``viewer/static`` directory."""
    return resources.files(PACKAGE).joinpath(STATIC_DIR)


def three_root() -> Traversable:
    """Return the vendored three.js directory."""
    return resources.files(PACKAGE).joinpath(*THREE_DIR.split("/"))


def _walk(root: Traversable, prefix: str) -> Iterator[tuple[str, Traversable]]:
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        relative = f"{prefix}{child.name}" if not prefix else f"{prefix}/{child.name}"
        if child.is_dir():
            yield from _walk(child, relative)
        elif child.is_file():
            yield relative, child


def iter_static_files() -> Iterator[tuple[str, Traversable]]:
    """Yield ``(asset_path, resource)`` for every shipped frontend file.

    ``asset_path`` always starts with ``assets/`` so it can be served or copied
    verbatim by both delivery modes.
    """
    for name, resource in _walk(static_root(), ""):
        yield f"assets/{name}", resource
    for name, resource in _walk(three_root(), ""):
        yield f"{THREE_PREFIX}{name}", resource


def resolve_static(asset_path: str) -> Traversable | None:
    """Resolve an ``assets/...`` path to a packaged file, or ``None``.

    Callers must already have validated the path segments; this function never
    resolves filesystem paths, so a crafted name cannot escape the package.
    """
    if not asset_path.startswith("assets/"):
        return None
    relative = asset_path[len("assets/") :]
    if not relative:
        return None
    if relative.startswith("three/"):
        root = three_root()
        relative = relative[len("three/") :]
    else:
        root = static_root()
    node: Traversable = root
    for segment in relative.split("/"):
        if segment in {"", ".", ".."}:
            return None
        node = node.joinpath(segment)
    return node if node.is_file() else None


def read_static(asset_path: str) -> bytes:
    """Read one packaged frontend file by its delivery URL path."""
    resource = resolve_static(asset_path)
    if resource is None:
        raise FileNotFoundError(asset_path)
    return resource.read_bytes()


__all__ = [
    "iter_static_files",
    "read_static",
    "resolve_static",
    "static_root",
    "three_root",
]
