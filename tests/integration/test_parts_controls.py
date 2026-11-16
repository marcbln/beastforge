"""Published control contracts for iron-warden (FR-008..FR-012)."""

from __future__ import annotations

import numpy as np

from beastforge.render import render


def test_iron_warden_controls_reference_real_joints(settings, tmp_path) -> None:
    outcome = render("iron-warden", settings=settings, out_dir=str(tmp_path), force=True)
    assert outcome.manifest is not None
    manifest = outcome.manifest
    joints = {joint.name for joint in manifest.skeleton.joints}

    controls = {
        control.address: control for part in manifest.parts for control in part.controls
    }
    assert controls
    for address, control in controls.items():
        assert control.joint in joints, address
        assert np.isclose(np.linalg.norm(control.axis), 1.0, atol=1e-6)
        assert (control.units == "deg") == (control.mode == "rotation")

    assert controls["left-leg/swing"].mode == "rotation"
    assert controls["left-leg/swing"].range is not None
    assert controls["rear-piston/extend"].mode == "translation"
    assert controls["rear-piston/extend"].units == "m"
    assert controls["shoulder-turret/yaw"].mode == "rotation"
    assert len(controls) == len(set(controls))
