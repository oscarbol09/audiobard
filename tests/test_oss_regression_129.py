"""Exit status of the doctor command with optional provider keys unset."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from audiobard.cli import app


@pytest.mark.parametrize(
    ("models", "ffmpeg_available", "expected_exit"),
    [
        (["qwen2.5:7b"], True, 0),
        ([], True, 1),
        (["qwen2.5:7b"], False, 1),
    ],
    ids=["offline-providers", "no-llm", "no-ffmpeg"],
)
def test_doctor_without_cloud_keys(
    models: list[str],
    ffmpeg_available: bool,
    expected_exit: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path))
    for key in (
        "OPENROUTER_API_KEY", "AUDIOBARD_OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "AUDIOBARD_GEMINI_API_KEY",
        "NVIDIA_NIM_API_KEY", "AUDIOBARD_NIM_API_KEY", "NIM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    response = httpx.Response(
        200,
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
        json={"models": [{"name": model} for model in models]},
    )
    with (
        patch("audiobard.doctor.httpx.get", return_value=response),
        patch("audiobard.doctor.find_piper", return_value="piper"),
        patch("audiobard.doctor.find_ffmpeg", return_value="ffmpeg" if ffmpeg_available else None),
    ):
        result = CliRunner().invoke(app, ["doctor"], catch_exceptions=False)

    assert result.exit_code == expected_exit, result.output
    for key in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "NVIDIA_NIM_API_KEY"):
        assert any(key in row and "not configured" in row for row in result.output.splitlines())
