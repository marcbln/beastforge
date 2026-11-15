"""The runtime must never reference an external host (FR-022, SC-007)."""

from __future__ import annotations

import posixpath
import re

from beastforge.viewer.assets import iter_static_files, resolve_static

EXTERNAL = re.compile(r"(?:from\s*|import\s*|fetch\(\s*|src\s*=\s*|href\s*=\s*)[\"']https?://")
ABSOLUTE_HTML = re.compile(r"(?:src|href)\s*=\s*[\"']https?://")
RELATIVE_IMPORT = re.compile(r"(?:from\s+|import\s*)\(?\s*[\"'](\.{1,2}/[^\"']+)[\"']")
MODULE_SRC = re.compile(r"<script[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']")
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)


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


def all_runtime_files() -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for path, resource in iter_static_files():
        if path.endswith((".js", ".mjs", ".html")):
            files.append((path, resource.read_text(encoding="utf-8")))
    return files


def test_every_relative_import_resolves_to_a_packaged_asset() -> None:
    """A vendored module split (e.g. three.core.js) must never be left behind."""
    assert all_runtime_files()
    for path, text in all_runtime_files():
        for specifier in RELATIVE_IMPORT.findall(text):
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), specifier))
            assert resolve_static(resolved) is not None, (
                f"{path} imports missing asset {specifier!r} (resolved to {resolved!r})"
            )


def test_module_scripts_are_external_for_strict_csp() -> None:
    index = dict(all_runtime_files())["assets/index.html"]
    assert INLINE_SCRIPT.search(index) is None, "strict CSP blocks inline <script>"
    for source in MODULE_SRC.findall(index):
        assert source.startswith("./"), source
        # The export installs index.html at the bundle root, so its refs are root-relative.
        resolved = posixpath.normpath(source.lstrip("./"))
        assert resolve_static(resolved) is not None, f"missing script {source!r}"
