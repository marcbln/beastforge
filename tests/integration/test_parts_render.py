"""End-to-end validate/render of the mech and craft example assemblies."""

from __future__ import annotations

import json
from pathlib import Path

from beastforge.config import Settings
from beastforge.render import render
from beastforge.viewer.catalog import build_catalog


def test_validate_reports_both_examples() -> None:
    # The CLI-level library gate is covered by the existing validate tests; here
    # we assert the catalog discovers both new assemblies.
    settings = Settings(library=str(Path(__file__).resolve().parents[2] / "library"))
    catalog = build_catalog(settings)
    names = {entry.name for entry in catalog.creatures}
    assert {"iron-warden", "hover-skiff"} <= names


def test_render_both_examples(settings, tmp_path) -> None:
    for name in ("iron-warden", "hover-skiff"):
        outcome = render(name, settings=settings, out_dir=str(tmp_path / name), force=True)
        assert outcome.glb is not None
        assert outcome.manifest is not None
        assert outcome.manifest.schemaVersion == "1.1"
        assert [part.name for part in outcome.manifest.parts]
        manifest_text = outcome.manifest_text
        assert manifest_text is not None
        payload = json.loads(manifest_text)
        assert payload["parts"]
        if name == "hover-skiff":
            baseline = [clip for clip in payload["clips"] if clip["name"] == "baseline"]
            assert baseline and baseline[0]["source"] == "automatic"
            assert [part["name"] for part in payload["parts"]] == [
                "hull",
                "left-wing",
                "right-wing",
                "engine",
                "rotor",
            ]
