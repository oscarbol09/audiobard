"""Smoke tests for the CLI entry point."""

from __future__ import annotations

from typer.testing import CliRunner

from audiobard.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "audiobard 0.1.0" in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # Typer exits 0 when help is shown explicitly, 2 when it falls back to
    # help after missing required args — both are "help was printed".
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


def test_unknown_command_fails() -> None:
    result = runner.invoke(app, ["definitely-not-a-command"])
    assert result.exit_code != 0
