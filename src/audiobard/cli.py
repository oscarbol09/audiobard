"""CLI entry point for audiobard.

The full command surface (`generate`, `benchmark`, `stats`, `voices`,
`validate-config`) lands with the v0.1.0 pipeline. This module currently
exposes `--version` so the package is installable and importable, and so CI
has a stable entry point to smoke-test.
"""

from __future__ import annotations

import typer

from audiobard import __version__

app = typer.Typer(
    name="audiobard",
    help="AI-powered audiobook generator (multi-character voice synthesis).",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"audiobard {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """AudioBard CLI."""


if __name__ == "__main__":
    main()
