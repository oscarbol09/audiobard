"""Tests for Piper TTS Provider."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from httpx import Response

from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.tts.piper_provider import (
    PiperProvider,
    find_piper,
    local_locale_counts,
)


@pytest.mark.asyncio
async def test_piper_list_voices() -> None:
    """Test that list_voices parses the voice file pool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        # Write dummy voice pool file
        pool_file = voices_dir / "en_US.json"
        pool_file.write_text(
            """[
            {"id": "en_US-dummy-medium", "locale": "en_US",
             "gender": "male", "age": "adult", "energy": 0.5}
        ]""",
            encoding="utf-8",
        )

        config = AudioBardConfig(
            cache_dir=tmp_path,
            voices_dir=voices_dir,
            db_path=tmp_path / "test.db",
        )

        provider = PiperProvider(config)
        voices = await provider.list_voices("en_US")
        assert len(voices) == 1
        assert voices[0].id == "en_US-dummy-medium"
        assert voices[0].gender == GenderHint.MALE


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_downloads_if_missing() -> None:
    """Test that ensure_model downloads missing voice files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        # Mock download URLs
        base_url = (
            "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
            "en/en_US/dummy/medium/en_US-dummy-medium"
        )
        respx.get(f"{base_url}.onnx").mock(
            return_value=Response(200, content=b"onnx-data")
        )
        respx.get(f"{base_url}.onnx.json").mock(
            return_value=Response(200, content=b'{"config": true}')
        )

        provider = PiperProvider(config)
        onnx_file = await provider._ensure_model("en_US-dummy-medium")

        assert onnx_file.exists()
        assert onnx_file.read_bytes() == b"onnx-data"
        assert (tmp_path / "piper" / "en_US-dummy-medium.onnx.json").exists()


@pytest.mark.asyncio
@patch("shutil.which")
@patch("asyncio.create_subprocess_exec")
async def test_piper_synthesize_raw(
    mock_subproc: AsyncMock, mock_which: AsyncMock
) -> None:
    """Test that subprocess is run correctly and returns converted MP3 bytes."""
    mock_which.return_value = "/usr/bin/piper"

    # Mock subprocess return value
    # Piper outputs WAV. We will mock the output to be a valid basic WAV header + silent bytes,
    # so that pydub doesn't fail to decode it.
    # Standard 44-byte WAV header:
    wav_header = (
        b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x22\x56\x00\x00\x44\xAC\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
        b"\x00\x00\x00\x00"
    )

    mock_process = AsyncMock()
    mock_process.communicate.return_value = (wav_header, b"")
    mock_process.returncode = 0
    mock_subproc.return_value = mock_process

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = AudioBardConfig(
            cache_dir=tmp_path,
            db_path=tmp_path / "test.db",
        )

        # Pre-seed cached voice files so we don't try to download them
        piper_dir = tmp_path / "piper"
        piper_dir.mkdir()
        (piper_dir / "en_US-dummy-medium.onnx").write_bytes(b"onnx-data")
        (piper_dir / "en_US-dummy-medium.onnx.json").write_bytes(b"{}")

        provider = PiperProvider(config)
        voice = Voice(
            id="en_US-dummy-medium",
            locale="en_US",
            gender=GenderHint.MALE,
            age=AgeHint.ADULT,
        )

        # Override ensure_model call to avoid checks
        with patch.object(
            provider, "_ensure_model", return_value=piper_dir / "en_US-dummy-medium.onnx"
        ):
            mp3_bytes = await provider._synthesize_raw(
                "Hello", voice, Emotion.HAPPY, rate=1.1, pitch=1.0
            )

            # verify that the conversion yielded non-empty audio output bytes
            assert len(mp3_bytes) > 0
            assert mock_subproc.called

            # Check that length_scale was set according to rate
            # (1 / (1.1 * happy_emotion_rate(1.1)))
            # happy_emotion_rate = 1.10
            # final_rate = 1.1 * 1.1 = 1.21
            # length_scale = 1.0 / 1.21 = 0.826
            called_args = mock_subproc.call_args[0]
            assert called_args[0] == "/usr/bin/piper"
            assert "--length_scale" in called_args
            scale_idx = called_args.index("--length_scale")
            assert called_args[scale_idx + 1] == "0.826"


@pytest.mark.asyncio
async def test_piper_list_voices_missing_pool(tmp_path: Path) -> None:
    config = AudioBardConfig(
        cache_dir=tmp_path,
        voices_dir=tmp_path / "nonexistent_voices",
        db_path=tmp_path / "test.db",
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []


@pytest.mark.asyncio
@patch("shutil.which", return_value=None)
async def test_piper_missing_executable(mock_which: Any, tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)
    with pytest.raises(FileNotFoundError, match="piper executable not found"):
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)


@pytest.mark.asyncio
@patch("shutil.which", return_value="/usr/bin/piper")
@patch("asyncio.create_subprocess_exec")
async def test_piper_subprocess_error(
    mock_subproc: AsyncMock, mock_which: Any, tmp_path: Path
) -> None:
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Piper internal error")
    mock_subproc.return_value = mock_proc

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)

    with (
        patch.object(provider, "_ensure_model", return_value=tmp_path / "v1.onnx"),
        pytest.raises(RuntimeError, match="Piper process exited with code 1"),
    ):
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)


@pytest.mark.asyncio
async def test_piper_list_voices_not_list(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US.json").write_text('{"not": "a list"}', encoding="utf-8")
    config = AudioBardConfig(
        cache_dir=tmp_path, voices_dir=voices_dir, db_path=tmp_path / "test.db"
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []


@pytest.mark.asyncio
async def test_piper_list_voices_invalid_json(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US.json").write_text("invalid json content", encoding="utf-8")
    config = AudioBardConfig(
        cache_dir=tmp_path, voices_dir=voices_dir, db_path=tmp_path / "test.db"
    )
    provider = PiperProvider(config)
    assert await provider.list_voices("en_US") == []



@pytest.mark.asyncio
async def test_piper_ensure_model_cached(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)
    onnx_file = piper_dir / "en_US-dummy-medium.onnx"
    json_file = piper_dir / "en_US-dummy-medium.onnx.json"
    onnx_file.write_bytes(b"cached-onnx")
    json_file.write_bytes(b"{}")

    provider = PiperProvider(config)
    result = await provider._ensure_model("en_US-dummy-medium")
    assert result == onnx_file


@pytest.mark.asyncio
async def test_piper_ensure_model_invalid_voice_id(tmp_path: Path) -> None:
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    with pytest.raises(ValueError, match="Invalid Piper voice ID format"):
        await provider._ensure_model("invalid_id")


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_concurrent_downloads_once(tmp_path: Path) -> None:
    """Concurrent _ensure_model calls must download each voice file only once."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)

    base_url = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_US/dummy/medium/en_US-dummy-medium"
    )
    onnx_route = respx.get(f"{base_url}.onnx").mock(
        return_value=Response(200, content=b"onnx-data")
    )
    json_route = respx.get(f"{base_url}.onnx.json").mock(
        return_value=Response(200, content=b'{"config": true}')
    )

    results = await asyncio.gather(
        provider._ensure_model("en_US-dummy-medium"),
        provider._ensure_model("en_US-dummy-medium"),
        provider._ensure_model("en_US-dummy-medium"),
    )

    assert len({p.resolve() for p in results}) == 1
    assert results[0].exists()
    assert results[0].read_bytes() == b"onnx-data"
    assert (tmp_path / "piper" / "en_US-dummy-medium.onnx.json").read_bytes() == (
        b'{"config": true}'
    )
    # Without the lock, each concurrent caller would hit the network.
    assert onnx_route.call_count == 1
    assert json_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_atomic_failure_cleanup(tmp_path: Path) -> None:
    """If model download fails midway, no partial tmp or target files should remain."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)

    base_url = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_US/dummy/medium/en_US-dummy-medium"
    )
    respx.get(f"{base_url}.onnx.json").mock(
        return_value=Response(200, content=b'{"config": true}')
    )
    respx.get(f"{base_url}.onnx").mock(
        return_value=Response(500, content=b"server error")
    )

    with pytest.raises(httpx.HTTPStatusError):
        await provider._ensure_model("en_US-dummy-medium")

    piper_dir = tmp_path / "piper"
    assert not (piper_dir / "en_US-dummy-medium.onnx").exists()
    assert not (piper_dir / "en_US-dummy-medium.onnx.json").exists()
    assert not list(piper_dir.glob("*.tmp"))


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_cleans_corrupt_zero_byte_cache(tmp_path: Path) -> None:
    """Zero-byte files in cache must be recognized as corrupted, deleted, and re-downloaded."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)

    # Seed 0-byte corrupted cache files
    corrupt_onnx = piper_dir / "en_US-dummy-medium.onnx"
    corrupt_json = piper_dir / "en_US-dummy-medium.onnx.json"
    corrupt_onnx.write_bytes(b"")
    corrupt_json.write_bytes(b"")

    base_url = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_US/dummy/medium/en_US-dummy-medium"
    )
    respx.get(f"{base_url}.onnx").mock(
        return_value=Response(200, content=b"valid-onnx-bytes")
    )
    respx.get(f"{base_url}.onnx.json").mock(
        return_value=Response(200, content=b'{"config": true}')
    )

    provider = PiperProvider(config)
    result = await provider._ensure_model("en_US-dummy-medium")

    assert result == corrupt_onnx
    assert corrupt_onnx.read_bytes() == b"valid-onnx-bytes"
    assert corrupt_json.read_bytes() == b'{"config": true}'


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_rejects_empty_download(tmp_path: Path) -> None:
    """Empty response body from remote must raise ValueError and not commit to cache."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)

    base_url = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_US/dummy/medium/en_US-dummy-medium"
    )
    respx.get(f"{base_url}.onnx.json").mock(
        return_value=Response(200, content=b"")
    )

    with pytest.raises(ValueError, match="Received empty response"):
        await provider._ensure_model("en_US-dummy-medium")

    piper_dir = tmp_path / "piper"
    assert not (piper_dir / "en_US-dummy-medium.onnx.json").exists()


@pytest.mark.asyncio
@respx.mock
async def test_piper_ensure_model_concurrent_separate_instances(tmp_path: Path) -> None:
    """Distinct PiperProvider instances downloading concurrently must not collide on temp files."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider1 = PiperProvider(config)
    provider2 = PiperProvider(config)

    base_url = (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_US/dummy/medium/en_US-dummy-medium"
    )
    respx.get(f"{base_url}.onnx").mock(
        return_value=Response(200, content=b"concurrent-onnx-bytes")
    )
    respx.get(f"{base_url}.onnx.json").mock(
        return_value=Response(200, content=b'{"config": true}')
    )

    p1_res, p2_res = await asyncio.gather(
        provider1._ensure_model("en_US-dummy-medium"),
        provider2._ensure_model("en_US-dummy-medium"),
    )

    piper_dir = tmp_path / "piper"
    assert p1_res == piper_dir / "en_US-dummy-medium.onnx"
    assert p2_res == piper_dir / "en_US-dummy-medium.onnx"
    assert p1_res.read_bytes() == b"concurrent-onnx-bytes"
    assert not list(piper_dir.glob("*.tmp"))


_PIPER_ENV_VARS = ("AUDIOBARD_PIPER", "PIPER_BINARY", "PIPER_PATH")


def _clear_piper_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _PIPER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("env_name", _PIPER_ENV_VARS)
def test_find_piper_prefers_env_var(
    env_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A portable install pointing one of the env vars must win over PATH."""
    binary = tmp_path / "piper-local"
    binary.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv(env_name, str(binary))
    with patch("shutil.which", return_value=None):
        assert find_piper() == str(binary.resolve())


def test_find_piper_ignores_env_var_pointing_at_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale env var must not mask a working PATH install."""
    monkeypatch.setenv("AUDIOBARD_PIPER", str(tmp_path / "does-not-exist"))
    with patch("shutil.which", return_value="/usr/local/bin/piper"):
        assert find_piper() == "/usr/local/bin/piper"


def test_find_piper_uses_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_piper_env(monkeypatch)
    with patch("shutil.which", return_value="/usr/local/bin/piper"):
        assert find_piper() == "/usr/local/bin/piper"


@pytest.mark.parametrize("subdir", [Path("tools") / "piper", Path("tools") / "bin", Path("tools")])
def test_find_piper_falls_back_to_bundled_tools_dir(
    subdir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A piper binary bundled under tools/ (portable install) must be found."""
    _clear_piper_env(monkeypatch)
    name = "piper.exe" if sys.platform == "win32" else "piper"
    binary = tmp_path / subdir / name
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"#!/bin/sh\n")
    monkeypatch.chdir(tmp_path)
    with patch("shutil.which", return_value=None):
        assert find_piper() == str(binary.resolve())


def test_find_piper_returns_none_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_piper_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    with patch("shutil.which", return_value=None):
        assert find_piper() is None


@pytest.mark.asyncio
async def test_piper_synthesize_uses_env_var_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (#108): an env-var-resolved binary must be spawned.

    Before the fix _synthesize_raw only called shutil.which("piper"), so a
    portable install with AUDIOBARD_PIPER set raised FileNotFoundError even
    though the binary was present.
    """
    binary = tmp_path / "piper-local"
    binary.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv("AUDIOBARD_PIPER", str(binary))

    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)

    with (
        patch("shutil.which", return_value=None),
        patch.object(provider, "_ensure_model", return_value=tmp_path / "v1.onnx"),
        patch("audiobard.tts.piper_provider._wav_to_mp3", return_value=b"mp3-bytes"),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subproc,
    ):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"wav-bytes", b"")
        mock_subproc.return_value = mock_proc

        data = await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)

    assert data == b"mp3-bytes"
    assert mock_subproc.call_args[0][0] == str(binary.resolve())


@pytest.mark.asyncio
async def test_piper_kills_subprocess_when_cancelled(tmp_path: Path) -> None:
    """A cancelled synthesis must not leave an orphan piper process."""
    config = AudioBardConfig(cache_dir=tmp_path, db_path=tmp_path / "test.db")
    provider = PiperProvider(config)
    voice = Voice(id="v1", locale="en_US", gender=GenderHint.MALE, age=AgeHint.ADULT)

    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=asyncio.CancelledError())
    proc.wait = AsyncMock()
    proc.kill = MagicMock()

    with (
        patch("audiobard.tts.piper_provider.find_piper", return_value="/usr/bin/piper"),
        patch.object(provider, "_ensure_model", return_value=tmp_path / "v1.onnx"),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subproc,
        pytest.raises(asyncio.CancelledError),
    ):
        mock_subproc.return_value = proc
        await provider._synthesize_raw("Hello", voice, Emotion.NEUTRAL, 1.0, 1.0)

    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()


def test_local_locale_counts_counts_pool_files(tmp_path: Path) -> None:
    (tmp_path / "en_US.json").write_text('[{"id": "a"}, {"id": "b"}]', encoding="utf-8")
    (tmp_path / "es_ES.json").write_text('[{"id": "c"}]', encoding="utf-8")
    (tmp_path / "empty.json").write_text("[]", encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    assert local_locale_counts(tmp_path) == {"en_US": 2, "es_ES": 1}


def test_local_locale_counts_missing_directory(tmp_path: Path) -> None:
    assert local_locale_counts(tmp_path / "nope") == {}


@pytest.mark.asyncio
async def test_piper_available_locales_uses_voices_dir(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US.json").write_text('[{"id": "a"}]', encoding="utf-8")
    config = AudioBardConfig(
        cache_dir=tmp_path, voices_dir=voices_dir, db_path=tmp_path / "test.db"
    )

    assert await PiperProvider(config).available_locales() == {"en_US": 1}


