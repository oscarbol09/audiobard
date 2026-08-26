from unittest.mock import Mock, patch

import httpx

from audiobard.doctor import collect_diagnostics


def test_collect_diagnostics_reports_dependencies_and_redacts_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-value")
    response = Mock()
    response.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
    response.raise_for_status.return_value = None
    with (
        patch("audiobard.doctor.shutil.which", side_effect=["/usr/bin/ffmpeg", "/usr/bin/piper"]),
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


def test_collect_diagnostics_handles_ollama_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path))
    with (
        patch("audiobard.doctor.shutil.which", return_value=None),
        patch("audiobard.doctor.httpx.get", side_effect=httpx.ConnectError("offline")),
    ):
        rows = collect_diagnostics()
    values = {name: status for name, status, _ in rows}
    assert values["ollama"] == "missing"
    assert values["ffmpeg"] == "missing"
    assert values["piper"] == "missing"
