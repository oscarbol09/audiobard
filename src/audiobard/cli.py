"""CLI entry point for audiobard."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from audiobard import __version__
from audiobard.config import AudioBardConfig
from audiobard.models import Voice
from audiobard.pipeline import AudioBookPipeline, create_tts_provider

app = typer.Typer(
    name="audiobard",
    help="AI-powered audiobook generator (multi-character voice synthesis).",
    no_args_is_help=True,
)

console = Console()


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
    # Setup standard rich logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command("generate")
def generate(
    book: Path = typer.Argument(
        ...,
        help="Path to the book file (.txt or .epub).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("audiobook.mp3"),
        "--output",
        "-o",
        help="Path to write the output audiobook file (.mp3 or .m4b).",
    ),
    llm: str | None = typer.Option(
        None,
        "--llm",
        help="LLM provider to use (ollama, gemini, openrouter).",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="LLM model identifier to use.",
    ),
    tts: str | None = typer.Option(
        None,
        "--tts",
        help="TTS provider to use (piper, edge).",
    ),
    locale: str | None = typer.Option(
        None,
        "--locale",
        help="TTS voice locale (e.g. en_US).",
    ),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Resume generation from the last successful checkpoint.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Perform parsing, character extraction, and mapping without voice synthesis.",
    ),
) -> None:
    """Generate a multi-character audiobook from a book file."""
    # 1. Load config and override with CLI args
    config_overrides: dict[str, object] = {}
    if llm:
        config_overrides["llm_provider"] = llm
    if model:
        config_overrides["llm_model"] = model
    if tts:
        config_overrides["tts_provider"] = tts
    if locale:
        config_overrides["tts_locale"] = locale

    try:
        config = AudioBardConfig.model_validate(config_overrides)
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # 2. Check commercial usage safety
    try:
        config.assert_commercial_safe()
    except RuntimeError as exc:
        console.print(f"[red]Ethics Guardrail Violation:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # 3. Setup logging level
    logging.getLogger().setLevel(config.log_level)

    # 4. Run pipeline
    pipeline = AudioBookPipeline(config)
    try:
        asyncio.run(pipeline.run(book, output, resume=resume, dry_run=dry_run))
    except Exception as exc:
        console.print(f"[red]Pipeline execution failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("voices")
def voices(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="TTS provider to list voices for (piper, edge).",
    ),
    locale: str | None = typer.Option(
        None,
        "--locale",
        "-l",
        help="Locale to filter voices (e.g. en_US).",
    ),
) -> None:
    """List available TTS voices for a provider and locale."""
    config_overrides: dict[str, object] = {}
    if provider:
        config_overrides["tts_provider"] = provider
    if locale:
        config_overrides["tts_locale"] = locale

    try:
        config = AudioBardConfig.model_validate(config_overrides)
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    tts_prov = create_tts_provider(config)

    async def list_them() -> list[Voice]:
        return await tts_prov.list_voices(config.tts_locale)

    try:
        voice_list = asyncio.run(list_them())
    except Exception as exc:
        console.print(f"[red]Failed to retrieve voices:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not voice_list:
        console.print(
            f"[yellow]No voices found for locale: {config.tts_locale}[/yellow]"
        )
        return

    table = Table(
        title=f"Voices ({config.tts_provider} — {config.tts_locale})"
    )
    table.add_column("Voice ID", style="cyan")
    table.add_column("Gender", style="magenta")
    table.add_column("Age Hint", style="green")
    table.add_column("Energy", style="yellow")

    for v in voice_list:
        table.add_row(
            v.id,
            v.gender.value,
            v.age.value,
            f"{v.energy:.2f}",
        )

    console.print(table)


@app.command("validate-config")
def validate_config() -> None:
    """Validate current configuration settings and environment variables."""
    try:
        config = AudioBardConfig()
    except Exception as exc:
        console.print(f"[red]Configuration validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        config.assert_commercial_safe()
    except RuntimeError as exc:
        console.print(f"[red]Commercial use assertion failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="AudioBard Configuration Settings")
    table.add_column("Setting Key", style="cyan")
    table.add_column("Value", style="green")

    for key, val in config.model_dump().items():
        table.add_row(key, str(val))

    console.print(table)
    console.print("[green]Configuration is valid and safe![/green]")


if __name__ == "__main__":
    app()
