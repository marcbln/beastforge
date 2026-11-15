"""Showroom accept/compare and its JSON surface."""

from __future__ import annotations

import json

import jsonschema

from beastforge.showroom.runner import run_showroom
from tests.conftest import ROOT


def _schema() -> dict:
    return json.loads(
        (
            ROOT
            / "specs/001-procedural-creature-generator/contracts/schema/showroom.result.schema.json"
        ).read_text()
    )


def test_accept_then_compare_passes(settings, monkeypatch, tmp_path) -> None:
    import beastforge.showroom.runner as runner

    base = tmp_path / "reference"
    monkeypatch.setattr(runner, "reference_base", lambda settings, cwd=None: base)
    accepted = run_showroom(["chitter-mite"], settings=settings, accept=True)
    assert accepted.ok is True
    assert accepted.report.mode == "accept"
    assert (base / "chitter-mite" / "frames").is_dir()
    assert (base / "chitter-mite" / "structural.json").is_file()

    compared = run_showroom(["chitter-mite"], settings=settings, accept=False)
    assert compared.ok is True
    assert compared.report.creatures[0].comparison.status == "pass"
    assert compared.report.creatures[0].comparison.differing_frames == []
    from beastforge.model.manifest import showroom_json

    jsonschema.validate(showroom_json(compared.report), _schema())


def test_missing_baseline_reports_no_baseline(settings, monkeypatch, tmp_path) -> None:
    import beastforge.showroom.runner as runner

    monkeypatch.setattr(runner, "reference_base", lambda settings, cwd=None: tmp_path / "empty")
    outcome = run_showroom(["chitter-mite"], settings=settings, accept=False)
    assert outcome.ok is False
    assert outcome.report.creatures[0].comparison.status == "no-baseline"
