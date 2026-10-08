"""CLI entry point for audiobard."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from audiobard import __version__
from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, GenderHint, Voice, VoicePreset, coerce_emotion
from audiobard.persistence import PersistenceManager
from audiobard.pipeline import (
    AudioBookPipeline,
    create_tts_provider,
    load_voice_preset,
    save_voice_preset,
)
from audiobard.tts.base import TTSProvider

app = typer.Typer(
    name="audiobard",
    help="AI-powered audiobook generator (multi-character voice synthesis).",
    no_args_is_help=True,
)

console = Console()
logger = logging.getLogger(__name__)

# How many locale names an error hint shows before summarising the rest.
_LOCALE_HINT_LIMIT = 20


def _known_locales(tts_prov: TTSProvider) -> dict[str, int]:
    """Best-effort offline locale enumeration for a provider; never raises."""
    try:
        counts = asyncio.run(tts_prov.available_locales())
    except Exception as exc:
        logger.debug("Locale enumeration failed: %s", exc)
        return {}
    if not isinstance(counts, dict):
        return {}
    safe: dict[str, int] = {}
    for locale, count in counts.items():
        try:
            safe[str(locale)] = int(count)
        except (TypeError, ValueError):
            continue
    return safe


def _locale_hint(counts: dict[str, int]) -> str:
    """Render the available-locales hint used in error messages."""
    if not counts:
        return ""
    names = sorted(counts)
    preview = ", ".join(names[:_LOCALE_HINT_LIMIT])
    if len(names) > _LOCALE_HINT_LIMIT:
        preview += f", ... ({len(names)} total)"
    return preview


def _ensure_locale_available(config: AudioBardConfig, tts_prov: TTSProvider) -> None:
    """Abort early when *config.tts_locale* has no voices for *tts_prov*.

    Only enforced when the provider can enumerate its locales offline: an empty
    mapping means "unknown", not "no such locale".
    """
    counts = _known_locales(tts_prov)
    if not counts or config.tts_locale in counts:
        return
    console.print(
        f"[red]Locale {config.tts_locale} has no voices available for the "
        f"{config.tts_provider} provider.[/red]"
    )
    hint = _locale_hint(counts)
    if hint:
        console.print(f"Available locales: {hint}")
    raise typer.Exit(code=1)


# Default audition text: short enough to sound instant, long enough to judge timbre.
DEFAULT_VOICE_TEST_TEXT = "This is a voice preview."


def _resolve_voice(voice_id: str, locale: str, known: list[Voice]) -> Voice:
    """Return the catalog entry for *voice_id*, or a placeholder when unknown.

    The placeholder keeps ``voices test`` usable when the voice pool file for a
    locale has not been generated yet; only the id and locale matter to the
    underlying providers.
    """
    for candidate in known:
        if candidate.id == voice_id:
            return candidate
    return Voice(
        id=voice_id,
        locale=locale,
        gender=GenderHint.NEUTRAL,
        age=AgeHint.ADULT,
    )


def _play_audio(path: Path) -> bool:
    """Play *path* with the platform audio player. Returns False if none launched."""
    import subprocess
    import sys

    if sys.platform == "darwin":
        cmd = ["afplay", str(path)]
    elif sys.platform == "win32":
        cmd = ["cmd", "/c", "start", "", str(path)]
    else:
        cmd = ["xdg-open", str(path)]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


voices_app = typer.Typer(
    name="voices",
    help="List available TTS voices, or audition a single voice.",
    invoke_without_command=True,
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
    # Setup standard rich logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command("doctor")
def doctor() -> None:
    """Check external dependencies and local configuration."""
    from audiobard.doctor import collect_diagnostics

    table = Table(title="AudioBard Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail")
    failed = False
    for name, status, detail in collect_diagnostics():
        style = "green" if status == "ok" or status == "configured" else "yellow"
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)
        failed |= status in {"missing", "error"}
    console.print(table)
    if failed:
        raise typer.Exit(code=1)


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
        help="TTS provider to use (piper, edge, kokoro).",
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
    chunk_words: int | None = typer.Option(
        None,
        "--chunk-words",
        help="Words per LLM attribution chunk.",
    ),
    llm_temperature: float | None = typer.Option(
        None,
        "--llm-temperature",
        help="Sampling temperature for LLM.",
    ),
    log_level: str | None = typer.Option(
        None,
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    ),
    voice_preset: Path | None = typer.Option(
        None,
        "--voice-preset",
        help="Apply a saved voice preset (.json) instead of re-mapping voices.",
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
    if chunk_words is not None:
        config_overrides["chunk_words"] = chunk_words
    if llm_temperature is not None:
        config_overrides["llm_temperature"] = llm_temperature
    if log_level is not None:
        config_overrides["log_level"] = log_level

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

    # 4. Load an optional voice preset so a series keeps the same voices
    preset: VoicePreset | None = None
    if voice_preset is not None:
        try:
            preset = load_voice_preset(voice_preset)
        except Exception as exc:
            console.print(f"[red]Could not read voice preset:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(
            f"Using voice preset [cyan]{voice_preset}[/cyan] "
            f"({len(preset.assignments)} assignments)"
        )

    # 5. Fail fast when the provider has no voices for the requested locale
    _ensure_locale_available(config, create_tts_provider(config))

    # 6. Run pipeline
    pipeline = AudioBookPipeline(config)
    try:
        asyncio.run(pipeline.run(book, output, resume=resume, dry_run=dry_run, voice_preset=preset))
    except Exception as exc:
        console.print(f"[red]Pipeline execution failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@voices_app.callback()
def voices(
    ctx: typer.Context,
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="TTS provider to list voices for (piper, edge, kokoro).",
    ),
    locale: str | None = typer.Option(
        None,
        "--locale",
        "-l",
        help="Locale to filter voices (e.g. en_US).",
    ),
) -> None:
    """List available TTS voices for a provider and locale.

    With no subcommand this lists voices; use ``audiobard voices test`` to
    audition a single voice without generating a whole book.
    """
    # Subcommands inherit these as defaults (``voices --provider edge test ...``).
    ctx.obj = {"provider": provider, "locale": locale}
    if ctx.invoked_subcommand is not None:
        return

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
        console.print(f"[yellow]No voices found for locale: {config.tts_locale}[/yellow]")
        hint = _locale_hint(_known_locales(tts_prov))
        if hint:
            console.print(f"Available locales: {hint}")
        return

    table = Table(title=f"Voices ({config.tts_provider} — {config.tts_locale})")
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


@voices_app.command("test")
def voices_test(
    ctx: typer.Context,
    voice: str = typer.Option(
        ...,
        "--voice",
        "-v",
        help="Voice ID to audition (e.g. en_US-amy-medium).",
    ),
    text: str = typer.Option(
        DEFAULT_VOICE_TEST_TEXT,
        "--text",
        "-t",
        help="Text to synthesize (keep it short).",
    ),
    emotion: str = typer.Option(
        "neutral",
        "--emotion",
        "-e",
        help="Emotion label or synonym to apply (e.g. cheerful).",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="TTS provider to audition (piper, edge, kokoro).",
    ),
    locale: str | None = typer.Option(
        None,
        "--locale",
        "-l",
        help="Locale the voice belongs to (e.g. en_US).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Where to write the sample MP3 (defaults to a temp file).",
    ),
    play: bool = typer.Option(
        True,
        "--play/--no-play",
        help="Play the sample with the system audio player.",
    ),
) -> None:
    """Synthesize a short sample with one voice and play it immediately."""
    inherited = ctx.obj if isinstance(ctx.obj, dict) else {}
    provider = provider or inherited.get("provider")
    locale = locale or inherited.get("locale")

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

    async def synthesize_sample() -> tuple[bytes, Voice]:
        known = await tts_prov.list_voices(config.tts_locale)
        target = _resolve_voice(voice, config.tts_locale, known)
        audio = await tts_prov.synthesize(
            text=text,
            voice=target,
            emotion=coerce_emotion(emotion),
        )
        return audio, target

    target_emotion = coerce_emotion(emotion)
    try:
        audio_bytes, target_voice = asyncio.run(synthesize_sample())
    except Exception as exc:
        console.print(f"[red]Voice audition failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not audio_bytes:
        console.print("[red]Voice audition failed:[/red] the provider returned no audio.")
        raise typer.Exit(code=1)

    destination = (
        output
        if output is not None
        else Path(tempfile.gettempdir()) / f"audiobard-voice-{voice}.mp3"
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(audio_bytes)
    except OSError as exc:
        console.print(f"[red]Could not write the sample:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Synthesized[/green] {target_voice.id} "
        f"({target_voice.locale}) with {target_emotion.value} emotion "
        f"— {len(audio_bytes)} bytes"
    )
    console.print(f"Sample written to: {destination}")

    if play and not _play_audio(destination):
        console.print("[yellow]No system audio player available — open the file above.[/yellow]")


app.add_typer(voices_app, name="voices")


@app.command("locales")
def locales(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="TTS provider to inspect (piper, edge, kokoro).",
    ),
) -> None:
    """List locales that have TTS voices available, with voice counts."""
    config_overrides: dict[str, object] = {}
    if provider:
        config_overrides["tts_provider"] = provider

    try:
        config = AudioBardConfig.model_validate(config_overrides)
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    counts = _known_locales(create_tts_provider(config))
    if not counts:
        console.print(
            "[yellow]No locales with locally available voices found for the "
            f"{config.tts_provider} provider.[/yellow]"
        )
        if config.tts_provider == "piper":
            console.print(
                f"Add a voice pool file under {config.voices_dir} "
                "(for example en_US.json) to enable a locale."
            )
        return

    console.print(f"Available locales for provider {config.tts_provider}:")
    table = Table(title="Locales with locally available voices")
    table.add_column("Locale", style="cyan")
    table.add_column("Voices", style="green")
    for locale in sorted(counts):
        table.add_row(locale, str(counts[locale]))
    table.add_row("[bold]Total[/bold]", f"[bold]{sum(counts.values())}[/bold]")
    console.print(table)


preset_app = typer.Typer(
    name="preset",
    help="Export and reuse custom voice presets.",
)


@preset_app.command("export")
def preset_export(
    book: Path = typer.Argument(
        ...,
        help="Path of a book that already has a stored voice mapping.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("voice-preset.json"),
        "--output",
        "-o",
        help="Where to write the preset JSON.",
    ),
    name: str = typer.Option(
        "",
        "--name",
        help="Optional label stored inside the preset.",
    ),
) -> None:
    """Export a book's saved voice mapping as a reusable preset."""
    try:
        config = AudioBardConfig()
    except Exception as exc:
        console.print(f"[red]Error loading configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    persistence = PersistenceManager(config.db_path)
    book_id = persistence.find_book_id(book)
    if book_id is None:
        console.print(
            f"[red]No stored record for {book}.[/red] Generate an audiobook from it first."
        )
        raise typer.Exit(code=1)

    assignments = persistence.get_voice_mapping(book_id)
    if not assignments:
        console.print(f"[red]{book} has no saved voice mapping to export.[/red]")
        raise typer.Exit(code=1)

    preset = VoicePreset.from_assignments(
        assignments,
        name=name,
        locale=config.tts_locale,
        provider=config.tts_provider,
    )
    try:
        save_voice_preset(output, preset)
    except OSError as exc:
        console.print(f"[red]Could not write the preset:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Exported {len(preset.assignments)} voice assignment(s)[/green] to {output}"
    )


app.add_typer(preset_app, name="preset")


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

    db_path = config.db_path
    if not db_path.exists():
        console.print("[yellow]No database found yet — run a generation first.[/yellow]")
        return

    persistence = PersistenceManager(db_path)
    db_stats = persistence.get_stats()

    # TTS cache disk usage
    tts_cache = config.cache_dir / "tts"
    tts_size_mb = (
        sum(f.stat().st_size for f in tts_cache.rglob("*.mp3")) / 1_048_576
        if tts_cache.exists()
        else 0.0
    )

    # Pipeline cache disk usage
    pipeline_cache = config.cache_dir / "pipeline"
    clips_count = len(list(pipeline_cache.rglob("*.mp3"))) if pipeline_cache.exists() else 0

    table = Table(title="AudioBard Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Books processed", str(db_stats["books"]))
    table.add_row("LLM cache entries", str(db_stats["llm_cache_entries"]))
    table.add_row("LLM cache hits", str(db_stats["llm_cache_hits"]))
    table.add_row("LLM cache hit rate", str(db_stats["llm_cache_hit_rate"]))
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
