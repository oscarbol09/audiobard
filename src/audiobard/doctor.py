"""Environment diagnostics for AudioBard."""

from __future__ import annotations

import os
import subprocess
from importlib.util import find_spec
from typing import Any

import httpx
from pydantic import ValidationError

from audiobard.audio.processor import find_ffmpeg
from audiobard.config import AudioBardConfig
from audiobard.tts.kokoro_provider import has_local_assets
from audiobard.tts.piper_provider import find_piper


def _key_row(name: str, setting: str, *aliases: str) -> tuple[str, str, str]:
    if any(os.getenv(key) for key in (name, *aliases)):
        return name, "configured", "environment"
    if setting:
        return name, "configured", "configuration"
    return name, "not configured", "optional"


def collect_diagnostics() -> list[tuple[str, str, str]]:
    """Return dependency checks as ``(name, status, detail)`` rows."""
    rows: list[tuple[str, str, str]] = []

    try:
        config = AudioBardConfig()
    except ValidationError:
        return [("configuration", "error", "invalid AudioBard settings")]

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        try:
            result = subprocess.run(
                [ffmpeg, "-version"], capture_output=True, text=True, check=False
            )
            version = result.stdout.splitlines()[0] if result.stdout else "version unavailable"
            rows.append(("ffmpeg", "ok" if result.returncode == 0 else "error", version))
        except OSError as exc:
            rows.append(("ffmpeg", "error", str(exc)))
    else:
        rows.append(
            (
                "ffmpeg",
                "missing",
                "not found on PATH, imageio_ffmpeg, or tools/",
            )
        )

    piper = find_piper()
    rows.append(
        (
            "piper",
            "ok" if piper else "missing",
            piper or "not found on PATH or tools/",
        )
    )

    ollama_ready = False
    try:
        response = httpx.get(f"{config.llm_base_url.rstrip('/')}/api/tags", timeout=2.0)
        response.raise_for_status()
        payload: Any = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = [
            model["name"] for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str) and model["name"]
        ] if isinstance(models, list) else []
        ollama_ready = bool(names)
        rows.append(("ollama", "ok" if names else "missing", ", ".join(names) or "no models"))
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        rows.append(("ollama", "missing", f"unavailable ({type(exc).__name__})"))

    keys = [
        _key_row("OPENROUTER_API_KEY", config.openrouter_api_key, "AUDIOBARD_OPENROUTER_API_KEY"),
        _key_row("GEMINI_API_KEY", config.gemini_api_key, "AUDIOBARD_GEMINI_API_KEY"),
        _key_row("NVIDIA_NIM_API_KEY", config.nim_api_key, "AUDIOBARD_NIM_API_KEY", "NIM_API_KEY"),
    ]
    rows.extend(keys)
    cloud_llm = not config.commercial_use and any(status == "configured" for _, status, _ in keys)
    if not (ollama_ready or cloud_llm):
        rows.append(("LLM provider", "error", "no available LLM provider"))

    cache_dir = config.cache_dir
    kokoro_installed = find_spec("kokoro_onnx") is not None
    kokoro_ready = kokoro_installed and has_local_assets(cache_dir)
    if kokoro_ready:
        rows.append(("kokoro", "ok", "model and voices available locally"))
    else:
        detail = "local model or voice pack missing" if kokoro_installed else "kokoro-onnx absent"
        rows.append(("kokoro", "missing", detail))
    edge = config.tts_provider == "edge" and not config.commercial_use
    if edge:
        rows.append(("edge", "configured", "requires internet"))
    if not (piper or kokoro_ready or edge):
        rows.append(("TTS provider", "error", "no available TTS provider"))

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        probe = cache_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        rows.append(("offline TTS directory", "ok", str(cache_dir)))
    except OSError as exc:
        rows.append(("offline TTS directory", "error", f"{cache_dir}: {exc}"))
    return rows
