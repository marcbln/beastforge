"""The only place that knows texforge exists (research D5, FR-021).

beastforge never synthesizes texture content. Validation resolves texforge
recipes by name; generation calls texforge in-process and captures the PNG bytes.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from beastforge.export.gltf import TextureImage
from beastforge.model.errors import BeastforgeError, NotFoundError
from beastforge.model.findings import ValidationFinding
from beastforge.model.recipe import Material, Recipe

SIZE_RE = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")


def parse_size(size: str) -> tuple[int, int]:
    """Parse ``WxH`` into integer pixel dimensions."""
    width, height = size.lower().split("x", 1)
    return int(width), int(height)


@dataclass
class MaterialCheck:
    """One material's resolution state during validation."""

    material: Material
    resolved: bool
    recipe_document: dict[str, Any] | None


class TexforgeLibrary:
    """A read-only view of a texforge recipe library."""

    def __init__(self, root: Path | None) -> None:
        self.root = root
        self._recipes: dict[str, dict[str, Any]] | None = None

    def recipes(self) -> dict[str, dict[str, Any]]:
        """Scan the library once per instance, keyed by texforge recipe name."""
        if self._recipes is not None:
            return self._recipes
        found: dict[str, dict[str, Any]] = {}
        if self.root is not None and self.root.is_dir():
            for path in sorted(self.root.glob("*/*.yaml")) + sorted(self.root.glob("*/*.yml")):
                try:
                    document = yaml.safe_load(path.read_text(encoding="utf-8"))
                except (OSError, yaml.YAMLError):
                    continue
                if not isinstance(document, dict):
                    continue
                meta = document.get("meta")
                if isinstance(meta, dict) and isinstance(meta.get("name"), str):
                    found.setdefault(meta["name"], document)
        self._recipes = found
        return found

    def _check_params(
        self, material: Material, document: dict[str, Any]
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        declared: dict[str, dict[str, Any]] = {}
        for param in document.get("params", []):
            if isinstance(param, dict) and isinstance(param.get("name"), str):
                declared[param["name"]] = param
        for key, value in material.params.items():
            if key not in declared:
                findings.append(
                    ValidationFinding(
                        code="material-param-invalid",
                        location={"recipe": "", "path": f"materials[{material.name}].params.{key}"},
                        message=(
                            f"texforge recipe {material.texture!r} does not declare "
                            f"parameter {key!r}."
                        ),
                        expected="one of: " + ", ".join(sorted(declared)),
                        actual=key,
                        remedy="Remove the override or use a declared texforge parameter.",
                    )
                )
                continue
            param = declared[key]
            expected_type = param.get("type")
            valid = True
            numeric = None
            if expected_type == "int":
                valid = isinstance(value, int) and not isinstance(value, bool)
                numeric = float(value) if valid else None
            elif expected_type == "float":
                valid = isinstance(value, (int, float)) and not isinstance(value, bool)
                numeric = float(value) if valid else None
            elif expected_type == "bool":
                valid = isinstance(value, bool)
            elif expected_type == "string":
                valid = isinstance(value, str)
            elif expected_type == "enum":
                valid = value in (param.get("values") or [])
            if not valid:
                findings.append(
                    ValidationFinding(
                        code="material-param-invalid",
                        location={"recipe": "", "path": f"materials[{material.name}].params.{key}"},
                        message=(
                            f"Value {value!r} for texforge parameter {key!r} is not a "
                            f"valid {expected_type}."
                        ),
                        expected=expected_type,
                        actual=value,
                        remedy="Use a value of the declared texforge parameter type.",
                    )
                )
                continue
            if numeric is not None:
                if param.get("min") is not None and numeric < float(param["min"]):
                    valid = False
                if param.get("max") is not None and numeric > float(param["max"]):
                    valid = False
                if not valid:
                    findings.append(
                        ValidationFinding(
                            code="material-param-invalid",
                            location={
                                "recipe": "",
                                "path": f"materials[{material.name}].params.{key}",
                            },
                            message=(
                                f"Value {value!r} for texforge parameter {key!r} is "
                                "outside its range."
                            ),
                            expected={"min": param.get("min"), "max": param.get("max")},
                            actual=value,
                            remedy="Choose a value inside the texforge parameter's limits.",
                        )
                    )
        return findings

    def check(
        self, material: Material, *, recipe_label: str = ""
    ) -> tuple[list[ValidationFinding], bool]:
        """Resolve a material reference and validate its overrides without rendering."""
        findings: list[ValidationFinding] = []
        path = f"materials[{material.name}]"
        if not SIZE_RE.match(material.size):
            findings.append(
                ValidationFinding(
                    code="material-size-invalid",
                    location={"recipe": recipe_label, "path": f"{path}.size"},
                    message=f"Material {material.name!r} size {material.size!r} is not WxH.",
                    expected="a positive WxH token such as 512x512",
                    actual=material.size,
                    remedy="Use a size like 512x512 or 256x256.",
                )
            )
        texture = material.texture
        if "/" in texture or "\\" in texture or texture.endswith((".yaml", ".yml")):
            findings.append(
                ValidationFinding(
                    code="material-unresolved",
                    location={"recipe": recipe_label, "path": f"{path}.texture"},
                    message=f"Material {material.name!r} names a path, not a texforge recipe.",
                    expected="a texforge recipe name",
                    actual=texture,
                    remedy="Reference the recipe by name, such as granite or brushed-steel.",
                )
            )
            return findings, False
        if self.root is None:
            findings.append(
                ValidationFinding(
                    code="material-unresolved",
                    location={"recipe": recipe_label, "path": f"{path}.texture"},
                    message=(
                        f"Cannot resolve texforge recipe {texture!r}: no texforge library found."
                    ),
                    expected="a readable texforge library",
                    actual="not found",
                    remedy="Pass --texforge-library or set BEASTFORGE_TEXFORGE_LIBRARY.",
                )
            )
            return findings, False
        document = self.recipes().get(texture)
        if document is None:
            findings.append(
                ValidationFinding(
                    code="material-unresolved",
                    location={"recipe": recipe_label, "path": f"{path}.texture"},
                    message=f"texforge recipe {texture!r} does not exist.",
                    expected="a recipe present in the texforge library",
                    actual=texture,
                    remedy="Run `texforge list` or use a name that exists in the texforge library.",
                )
            )
            return findings, False
        for finding in self._check_params(material, document):
            finding.location.recipe = recipe_label
            findings.append(finding)
        return findings, True

    def render_material(self, material: Material, *, staging_dir: Path) -> TextureImage:
        """Render one material in-process and return its PNG bytes and provenance."""
        if self.root is None:
            raise NotFoundError(
                "texforge-not-found",
                "No texforge library was found; cannot render materials.",
                location={"path": "materials"},
                remedy="Pass --texforge-library or set BEASTFORGE_TEXFORGE_LIBRARY.",
            )
        try:
            from texforge import __version__ as texforge_version  # noqa: F401
            from texforge.config import Settings as TexforgeSettings
            from texforge.model.errors import TexforgeError
            from texforge.render import render_recipe
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise NotFoundError(
                "texforge-not-found",
                f"texforge is not importable: {exc}",
                location={"path": "materials"},
                remedy="Install the texforge package (uv sync).",
            ) from exc

        with tempfile.NamedTemporaryFile(
            suffix=".png", prefix=f".tex-{material.name}-", dir=staging_dir, delete=False
        ) as handle:
            target = Path(handle.name)
        try:
            settings = TexforgeSettings(library_root=str(self.root))
            overrides = {key: str(value) for key, value in material.params.items()}
            payload = render_recipe(
                material.texture,
                settings=settings,
                output=target,
                overrides=overrides,
                size_override=material.size,
            )
            png = target.read_bytes()
        except TexforgeError as exc:
            code = {
                "recipe-not-found": "texture-not-found",
                "ambiguous-name": "texture-not-found",
                "param-type": "material-param-invalid",
                "param-out-of-range": "material-param-invalid",
                "undeclared-param": "material-param-invalid",
                "size-out-of-range": "material-size-invalid",
            }.get(exc.code, "material-render-failed")
            if exc.code in {"recipe-not-found", "ambiguous-name"}:
                raise NotFoundError(
                    code,
                    exc.finding.message,
                    location={"path": f"materials[{material.name}].texture"},
                    remedy="Check the texforge recipe name and its parameters.",
                ) from exc
            raise BeastforgeError(
                code,
                exc.finding.message,
                location={"path": f"materials[{material.name}]"},
                expected="a valid texforge recipe and parameters",
                actual=exc.code,
                remedy="Run `texforge validate <recipe>` to see the underlying problem.",
            ) from exc
        finally:
            target.unlink(missing_ok=True)

        sha256 = hashlib.sha256(png).hexdigest()
        reported = payload.get("output", {}).get("sha256")
        if reported is not None and reported != sha256:
            raise BeastforgeError(
                "material-render-failed",
                f"texforge reported sha256 {reported} but the PNG hashes to {sha256}.",
                location={"path": f"materials[{material.name}]"},
                remedy="This indicates a corrupt texforge install; reinstall dependencies.",
            )
        image = Image.open(BytesIO(png))
        width, height = image.size
        effective = payload.get("effective_params", material.params)
        return TextureImage(
            material=material.name,
            recipe=material.texture,
            params=dict(effective),
            size=material.size,
            width=width,
            height=height,
            sha256=sha256,
            png=png,
        )


def check_materials(
    recipe: Recipe,
    library: TexforgeLibrary,
    *,
    recipe_label: str,
) -> list[ValidationFinding]:
    """Check every material and flag ones no surface references."""
    findings: list[ValidationFinding] = []
    seen: set[str] = set()
    referenced = {surface.material for surface in recipe.surfaces if surface.material is not None}
    for material in recipe.materials:
        if material.name in seen:
            findings.append(
                ValidationFinding(
                    code="material-duplicate",
                    location={"recipe": recipe_label, "path": f"materials[{material.name}]"},
                    message=f"Material name {material.name!r} is declared more than once.",
                    expected="unique material names",
                    actual=material.name,
                    remedy="Rename one of the duplicate materials.",
                )
            )
        seen.add(material.name)
        material_findings, _resolved = library.check(material, recipe_label=recipe_label)
        findings.extend(material_findings)
        if material.name not in referenced:
            findings.append(
                ValidationFinding(
                    code="material-not-referenced",
                    severity="warning",
                    location={"recipe": recipe_label, "path": f"materials[{material.name}]"},
                    message=f"Material {material.name!r} is never referenced by a surface.",
                    expected="a surface that uses the material",
                    actual="unreferenced",
                    remedy="Reference it from a surface or remove the declaration.",
                )
            )
    for name in sorted(referenced - seen):
        findings.append(
            ValidationFinding(
                code="material-unresolved",
                location={"recipe": recipe_label, "path": "surfaces"},
                message=f"Surface material {name!r} is not declared in materials[].",
                expected="a declared material name",
                actual=name,
                remedy="Add the material declaration or fix the surface reference.",
            )
        )
    return findings


def texforge_version() -> str:
    """Return the installed texforge version, or ``unknown`` if unavailable."""
    try:
        from texforge import __version__

        return str(__version__)
    except ImportError:  # pragma: no cover - dependency is declared
        return "unknown"
