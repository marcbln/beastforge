"""GLB container and accessor layout."""

from __future__ import annotations

import json
import struct


def test_glb_header_and_chunks(rendered) -> None:
    data = rendered.glb
    assert data is not None
    magic, version, length = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67
    assert version == 2
    assert length == len(data)
    json_length, json_type = struct.unpack("<II", data[12:20])
    assert json_type == 0x4E4F534A
    assert json_length % 4 == 0
    document = json.loads(data[20 : 20 + json_length].decode("utf-8").rstrip(" "))
    bin_header = data[20 + json_length : 28 + json_length]
    bin_length, bin_type = struct.unpack("<II", bin_header)
    assert bin_type == 0x004E4942
    assert bin_length % 4 == 0
    assert "asset" in document
    assert document["asset"]["version"] == "2.0"


def test_accessors_are_aligned_and_images_are_png(rendered) -> None:
    data = rendered.glb
    json_length, _ = struct.unpack("<II", data[12:20])
    document = json.loads(data[20 : 20 + json_length].decode("utf-8").rstrip(" "))
    for view in document["bufferViews"]:
        assert view["byteOffset"] % 4 == 0
    assert document.get("images")
    assert all(image["mimeType"] == "image/png" for image in document["images"])


def test_animations_are_in_reserved_order(rendered) -> None:
    data = rendered.glb
    json_length, _ = struct.unpack("<II", data[12:20])
    document = json.loads(data[20 : 20 + json_length].decode("utf-8").rstrip(" "))
    names = [animation["name"] for animation in document["animations"]]
    assert names == ["idle", "locomotion", "attack", "hurt", "death"]
