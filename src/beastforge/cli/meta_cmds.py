"""``version`` and ``about`` commands (``cli:version`` / ``cli:about``)."""

from __future__ import annotations

from beastforge import __version__


def version_command() -> None:
    """Print ``beastforge <semver>`` and exit 0."""
    import typer

    typer.echo(f"beastforge {__version__}")


def about_command() -> None:
    """Print the one-screen about text (no configuration is read)."""
    import typer

    typer.echo(
        "\n".join(
            [
                f"beastforge {__version__}",
                "Offline, deterministic procedural 3D creature generator.",
                "Maintainer: beastforge maintainers",
                "License: MIT",
                "Repository: https://github.com/marc/beastforge",
                "Documentation: docs/architecture.md",
                "Cheat sheet: docs/cheatsheet-cli.md",
            ]
        )
    )
