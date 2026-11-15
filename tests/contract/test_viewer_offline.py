"""The runtime must never reference an external host (FR-022, SC-007)."""

from __future__ import annotations

import re

from beastforge.viewer.assets import iter_static_files

EXTERNAL = re.compile(r"(?:from\s*|import\s*|fetch\(\s*|src\s*=\s*|href\s*=\s*)[\"']https?://")
ABSOLUTE_HTML = re.compile(r"(?:src|href)\s*=\s*[\"']https?://")


def runtime_modules() -> list[tuple[str, str]]:
    modules: list[tuple[str, str]] = []
    for path, resource in iter_static_files():
        if path.startswith("assets/three/"):
            continue
        if path.endswith((".js", ".mjs", ".html", ".css")):
            modules.append((path, resource.read_text(encoding="utf-8")))
    return modules


def test_runtime_assets_have_no_external_references() -> None:
    modules = runtime_modules()
    assert modules
    for path, text in modules:
        assert not EXTERNAL.search(text), f"external URL in {path}"
        assert not ABSOLUTE_HTML.search(text), f"absolute host in {path}"


def test_index_imports_only_relative_assets() -> None:
    index = dict(runtime_modules())["assets/index.html"]
    for match in re.finditer(r"(?:src|href)\s*=\s*[\"']([^\"']+)", index):
        value = match.group(1)
        assert value.startswith(("./", "#")), f"non-relative reference {value!r} in index.html"
