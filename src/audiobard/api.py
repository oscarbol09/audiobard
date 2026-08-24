"""FastAPI application for AudioBard."""

from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException

from audiobard.config import AudioBardConfig
from audiobard.pipeline import AudioBookPipeline

app = FastAPI(title="AudioBard API", version="0.1.0")

LLMChoice = Literal["ollama", "gemini", "openrouter"]
TTSChoice = Literal["piper", "edge"]


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — Tauri queries this on startup."""
    return {"status": "ok"}


@app.get("/progress")
async def get_progress() -> dict[str, int]:
    """Get current generation progress (stub for future implementation)."""
    return {"progress": 0}


@app.post("/generate")
async def generate_audiobook(request: dict[str, Any]) -> dict[str, str]:
    """Generate audiobook from an uploaded base64-encoded file."""
    try:
        file_base64 = str(request["file_base64"])
        file_name = str(request["file_name"])
        llm_provider = cast(LLMChoice, str(request["llm_provider"]))
        llm_model = str(request["llm_model"])
        tts_provider = cast(TTSChoice, str(request["tts_provider"]))
        locale = str(request["locale"])

        raw_b64 = file_base64.split(",")[1] if "," in file_base64 else file_base64
        file_bytes = base64.b64decode(raw_b64)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_path = tmp_path / file_name
            input_path.write_bytes(file_bytes)

            output_dir = tmp_path / "output"
            output_dir.mkdir()

            config = AudioBardConfig(
                llm_provider=llm_provider,
                llm_model=llm_model,
                tts_provider=tts_provider,
                tts_locale=locale,
            )
            pipeline = AudioBookPipeline(config)

            output_path = output_dir / f"{input_path.stem}.mp3"
            await pipeline.run(input_path, output_path)

            if not output_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail="Audiobook generation failed - output file not found",
                )

            permanent_dir = Path.home() / "AudioBard" / "output"
            permanent_dir.mkdir(parents=True, exist_ok=True)
            permanent_path = permanent_dir / output_path.name
            shutil.copy2(output_path, permanent_path)
            return {"output_path": str(permanent_path)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {exc}",
        ) from exc
