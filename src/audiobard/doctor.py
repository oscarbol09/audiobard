"""Environment diagnostics for AudioBard."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

from audiobard.audio.processor import find_ffmpeg


def _key_state(*names: str) -> str:
    return "configured" if any(os.getenv(name) for name in names) else "missing"


def collect_diagnostics() -> list[tuple[str, str, str]]:
    """Return dependency checks as ``(name, status, detail)`` rows."""
    rows: list[tuple[str, str, str]] = []

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

    piper = shutil.which("piper")
    rows.append(("piper", "ok" if piper else "missing", piper or "not found on PATH"))

    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        response.raise_for_status()
        payload: Any = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = [str(model.get("name", "unknown")) for model in models if isinstance(model, dict)]
        rows.append(("ollama", "ok", ", ".join(names) if names else "running; no models"))
    except (httpx.HTTPError, ValueError) as exc:
        rows.append(("ollama", "missing", f"unavailable ({exc})"))

    rows.extend(
        [
            (
                "OPENROUTER_API_KEY",
                _key_state("OPENROUTER_API_KEY", "AUDIOBARD_OPENROUTER_API_KEY"),
                "environment",
            ),
            (
                "GEMINI_API_KEY",
                _key_state("GEMINI_API_KEY", "AUDIOBARD_GEMINI_API_KEY"),
                "environment",
            ),
            (
                "NVIDIA_NIM_API_KEY",
                _key_state("NVIDIA_NIM_API_KEY", "AUDIOBARD_NIM_API_KEY", "NIM_API_KEY"),
                "environment",
            ),
        ]
    )

    cache_dir = Path(os.getenv("AUDIOBARD_CACHE_DIR", Path.home() / ".cache" / "audiobard"))
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        probe = cache_dir / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        rows.append(("offline TTS directory", "ok", str(cache_dir)))
    except OSError as exc:
        rows.append(("offline TTS directory", "error", f"{cache_dir}: {exc}"))
    return rows
