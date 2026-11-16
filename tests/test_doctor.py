from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
from typer.testing import CliRunner

from audiobard.cli import app
from audiobard.doctor import collect_diagnostics


def test_collect_diagnostics_reports_dependencies_and_redacts_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-value")
    response = Mock()
    response.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
    response.raise_for_status.return_value = None
    with (
        patch("audiobard.doctor.find_ffmpeg", return_value="/usr/bin/ffmpeg"),
        patch("audiobard.doctor.find_piper", return_value="/usr/bin/piper"),
        patch("audiobard.doctor.subprocess.run") as run,
        patch("audiobard.doctor.httpx.get", return_value=response),
    ):
        run.return_value.stdout = "ffmpeg version 7.0"
        run.return_value.returncode = 0
        rows = collect_diagnostics()
    values = {name: (status, detail) for name, status, detail in rows}
    assert values["ffmpeg"][0] == "ok"
    assert values["piper"][0] == "ok"
    assert values["ollama"] == ("ok", "qwen2.5:7b")
    assert values["OPENROUTER_API_KEY"] == ("configured", "environment")
    assert "secret-value" not in str(rows)
    assert values["offline TTS directory"][0] == "ok"


def test_collect_diagnostics_handles_ollama_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path))
    with (
        patch("audiobard.doctor.find_ffmpeg", return_value=None),
        patch("audiobard.doctor.find_piper", return_value=None),
        patch("audiobard.doctor.httpx.get", side_effect=httpx.ConnectError("offline")),
    ):
        rows = collect_diagnostics()
    values = {name: status for name, status, _ in rows}
    assert values["ollama"] == "missing"
    assert values["ffmpeg"] == "missing"
    assert values["piper"] == "missing"


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
