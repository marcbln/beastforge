"""No two-sided rendering: emitted GLB materials and authored viewer JS."""

from __future__ import annotations

import json
import re
import struct

from beastforge.render import render
from tests.conftest import ROOT

STATIC = ROOT / "src/beastforge/viewer/static"
AUTHORED = [
    STATIC / "app.js",
    *sorted((STATIC / "lib").glob("*.js")),
]


def _glb_json(data: bytes) -> dict:
    magic, version, _length = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67
    assert version == 2
    chunk_length, chunk_type = struct.unpack("<II", data[12:20])
    assert chunk_type == 0x4E4F534A
    return json.loads(data[20 : 20 + chunk_length].decode("utf-8"))


def test_glb_materials_never_set_double_sided(settings, tmp_path) -> None:
    outcome = render("ridge-stalker", settings=settings, out_dir=str(tmp_path), force=True)
    assert outcome.glb is not None
    document = _glb_json(outcome.glb)
    for material in document.get("materials", []):
        assert material.get("doubleSided") is not True
        assert "doubleSided" not in material


def test_authored_viewer_js_never_selects_double_side() -> None:
    for path in AUTHORED:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bDoubleSide\b", text), path
