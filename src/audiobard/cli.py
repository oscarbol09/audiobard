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


@app.command("stats")
def stats() -> None:
    """Show LLM cache hit rate and TTS disk usage statistics."""
    try:
        config = AudioBardConfig()
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    import sqlite3

    db_path = config.db_path
    if not db_path.exists():
        console.print("[yellow]No database found yet — run a generation first.[/yellow]")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # LLM cache stats
        row = conn.execute(
            "SELECT COUNT(*) AS total, SUM(hits) AS total_hits FROM llm_cache"
        ).fetchone()
        total_entries = int(row["total"]) if row["total"] else 0
        total_hits = int(row["total_hits"]) if row["total_hits"] else 0
        hit_rate = (
            f"{100 * total_hits / (total_hits + total_entries):.1f}%"
            if (total_hits + total_entries) > 0
            else "n/a"
        )

        # Books processed
        books = int(
            conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        )

        # TTS cache disk usage
        tts_cache = config.cache_dir / "tts"
        tts_size_mb = (
            sum(f.stat().st_size for f in tts_cache.rglob("*.mp3")) / 1_048_576
            if tts_cache.exists()
            else 0.0
        )

        # Pipeline cache disk usage
        pipeline_cache = config.cache_dir / "pipeline"
        clips_count = (
            len(list(pipeline_cache.rglob("*.mp3")))
            if pipeline_cache.exists()
            else 0
        )
    finally:
        conn.close()

    table = Table(title="AudioBard Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Books processed", str(books))
    table.add_row("LLM cache entries", str(total_entries))
    table.add_row("LLM cache hits", str(total_hits))
    table.add_row("LLM cache hit rate", hit_rate)
    table.add_row("TTS cache size", f"{tts_size_mb:.1f} MB")
    table.add_row("Pipeline clips cached", str(clips_count))
    console.print(table)


@app.command("benchmark")
def benchmark(
    llm: str = typer.Option(
        "ollama",
        "--llm",
        help="LLM provider (ollama, gemini, openrouter)",
    ),
    model: str = typer.Option(
        "qwen2.5:7b",
        "--model",
        help="Model identifier to benchmark",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON (useful for CI)",
    ),
) -> None:
    """Run attribution accuracy benchmark against the P&P ch3 gold standard."""
    from pathlib import Path as _Path

    eval_script = _Path(__file__).resolve().parent.parent.parent / "eval" / "benchmark.py"
    if not eval_script.exists():
        console.print(f"[red]Benchmark script not found:[/red] {eval_script}")
        raise typer.Exit(code=1)

    argv = ["--llm", llm, "--model", model]
    if json_output:
        argv.append("--json")

    # Run via importlib to avoid subprocess overhead
    import importlib.util

    spec = importlib.util.spec_from_file_location("benchmark", eval_script)
    if spec is None or spec.loader is None:
        console.print("[red]Failed to load benchmark module.[/red]")
        raise typer.Exit(code=1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc: int = mod.main(argv)
    if rc != 0:
        raise typer.Exit(code=rc)


if __name__ == "__main__":
    app()
