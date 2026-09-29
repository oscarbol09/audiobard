"""Tests for the Kokoro-82M ONNX TTS provider (issue #111)."""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from pydub import AudioSegment
from typer.testing import CliRunner

from audiobard.cli import app
from audiobard.config import AudioBardConfig
from audiobard.models import AgeHint, Emotion, GenderHint, Voice
from audiobard.pipeline import TTS_PROVIDER_FACTORIES
from audiobard.tts.kokoro_provider import (
    INSTALL_HINT,
    KOKORO_LOCALES,
    MODEL_ENV_VAR,
    MODEL_URL,
    VOICES_ENV_VAR,
    VOICES_URL,
    KokoroProvider,
    locale_for_voice,
    read_voice_names,
    samples_to_mp3,
    voice_from_id,
)

runner = CliRunner()

_PACK_VOICES = [
    "af_alloy",
    "af_bella",
    "af_sarah",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bm_george",
    "ef_dora",
    "zf_xiaobei",
]


def _write_voice_pack(path: Path, names: list[str] | None = None) -> Path:
    """Write a minimal Kokoro voice pack.

    The real pack is an ``npz`` archive holding a ``voices`` name array and a
    ``styles`` tensor; numpy only appends ``.npz`` to string paths, so the file
    object form is used to keep the ``.bin`` name the provider expects.
    """
    names = list(_PACK_VOICES if names is None else names)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez(
            handle,
            voices=np.array(names, dtype="<U32"),
            styles=np.zeros((len(names), 1, 8), dtype=np.float32),
        )
    return path


def _config(tmp_path: Path, **overrides: Any) -> AudioBardConfig:
    defaults: dict[str, Any] = {
        "tts_provider": "kokoro",
        "cache_dir": tmp_path / "cache",
        "db_path": tmp_path / "test.db",
    }
    defaults.update(overrides)
    return AudioBardConfig(**defaults)


def _provider_with_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> KokoroProvider:
    """A provider whose assets are already on disk, so nothing is downloaded."""
    monkeypatch.setenv(VOICES_ENV_VAR, str(_write_voice_pack(tmp_path / "voices.bin")))
    monkeypatch.setenv(MODEL_ENV_VAR, str(_write_dummy_model(tmp_path / "model.onnx")))
    return KokoroProvider(_config(tmp_path))


def _write_dummy_model(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"onnx-weights")
    return path


class _FakeKokoro:
    """Stand-in for ``kokoro_onnx.Kokoro`` that records its create() calls."""

    def __init__(self, samples: Any = None, sample_rate: int = 24000) -> None:
        self.calls: list[dict[str, Any]] = []
        self.samples = np.zeros(sample_rate // 2, dtype=np.float32) if samples is None else samples
        self.sample_rate = sample_rate

    def create(self, text: str, **kwargs: Any) -> tuple[Any, int]:
        self.calls.append({"text": text, **kwargs})
        return self.samples, self.sample_rate


# --------------------------------------------------------------------- helpers


def test_locale_for_voice_maps_the_language_letter() -> None:
    assert locale_for_voice("af_sarah") == "en_US"
    assert locale_for_voice("bm_george") == "en_GB"
    assert locale_for_voice("zf_xiaobei") == "zh_CN"
    assert locale_for_voice("qq_weird") is None
    assert locale_for_voice("") is None


def test_voice_from_id_reads_the_gender_letter() -> None:
    female = voice_from_id("af_sarah", "en_US")
    assert (female.id, female.locale, female.gender) == ("af_sarah", "en_US", GenderHint.FEMALE)
    assert female.age is AgeHint.ADULT

    male = voice_from_id("bm_george", "en_GB")
    assert male.gender is GenderHint.MALE

    assert voice_from_id("ax_mystery", "en_US").gender is GenderHint.NEUTRAL


def test_read_voice_names_handles_missing_and_broken_packs(tmp_path: Path) -> None:
    assert read_voice_names(tmp_path / "nope.bin") == []

    broken = tmp_path / "broken.bin"
    broken.write_bytes(b"definitely not an npz archive")
    assert read_voice_names(broken) == []


def test_read_voice_names_returns_the_pack_contents(tmp_path: Path) -> None:
    pack = _write_voice_pack(tmp_path / "voices.bin")
    assert read_voice_names(pack) == sorted(_PACK_VOICES)


def test_samples_to_mp3_produces_decodable_audio() -> None:
    samples = np.sin(np.linspace(0, 40, 24000)).astype(np.float32) * 0.4
    payload = samples_to_mp3(samples, 24000)
    segment = AudioSegment.from_file(io.BytesIO(payload), format="mp3")
    assert abs(len(segment) - 1000) < 100


def test_samples_to_mp3_pitch_shift_shortens_playback() -> None:
    samples = np.zeros(24000, dtype=np.float32)
    shifted = samples_to_mp3(samples, 24000, pitch=1.5)
    segment = AudioSegment.from_file(io.BytesIO(shifted), format="mp3")
    assert abs(len(segment) - 667) < 100


# ------------------------------------------------------------------- provider


def test_kokoro_is_a_registered_tts_provider(tmp_path: Path) -> None:
    assert "kokoro" in TTS_PROVIDER_FACTORIES
    provider = TTS_PROVIDER_FACTORIES["kokoro"](_config(tmp_path))
    assert isinstance(provider, KokoroProvider)


def test_config_accepts_kokoro(tmp_path: Path) -> None:
    assert _config(tmp_path).tts_provider == "kokoro"


@pytest.mark.asyncio
async def test_list_voices_filters_by_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)

    american = await provider.list_voices("en_US")
    assert [voice.id for voice in american] == [
        "af_alloy",
        "af_bella",
        "af_sarah",
        "am_adam",
        "am_michael",
    ]
    assert american[0].gender is GenderHint.FEMALE

    assert [voice.id for voice in await provider.list_voices("en_GB")] == ["bf_emma", "bm_george"]
    assert [voice.id for voice in await provider.list_voices("zh_CN")] == ["zf_xiaobei"]


@pytest.mark.asyncio
async def test_list_voices_without_network_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed asset download must not raise, it just yields no voices."""
    monkeypatch.delenv(VOICES_ENV_VAR, raising=False)
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    provider = KokoroProvider(_config(tmp_path))

    with patch(
        "audiobard.tts.kokoro_provider._download",
        new=AsyncMock(side_effect=OSError("offline")),
    ):
        assert await provider.list_voices("en_US") == []


@pytest.mark.asyncio
async def test_list_voices_for_unsupported_locale_skips_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(VOICES_ENV_VAR, raising=False)
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    provider = KokoroProvider(_config(tmp_path))

    with patch("audiobard.tts.kokoro_provider._download", new=AsyncMock()) as download:
        assert await provider.list_voices("de_DE") == []
    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_available_locales_counts_the_local_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)

    counts = await provider.available_locales()
    assert counts["en_US"] == 5
    assert counts["en_GB"] == 2
    assert counts["zh_CN"] == 1
    assert "de_DE" not in counts


@pytest.mark.asyncio
async def test_available_locales_is_empty_without_a_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(VOICES_ENV_VAR, raising=False)
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    assert await KokoroProvider(_config(tmp_path)).available_locales() == {}


@pytest.mark.asyncio
async def test_ensure_assets_downloads_missing_files_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent callers must not race the same download twice."""
    monkeypatch.delenv(VOICES_ENV_VAR, raising=False)
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    provider = KokoroProvider(_config(tmp_path))

    def fake_download(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"asset")

    download = AsyncMock(side_effect=fake_download)
    with patch("audiobard.tts.kokoro_provider._download", new=download):
        results = await asyncio.gather(
            provider._ensure_assets(), provider._ensure_assets()
        )
    model_path, voices_path = results[0]
    assert results[0] == results[1]

    assert model_path.is_file() and voices_path.is_file()
    assert download.await_count == 2
    assert [call.args[0] for call in download.await_args_list] == [MODEL_URL, VOICES_URL]


@pytest.mark.asyncio
async def test_ensure_assets_reuses_cached_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)

    with patch("audiobard.tts.kokoro_provider._download", new=AsyncMock()) as download:
        model_path, voices_path = await provider._ensure_assets()

    download.assert_not_awaited()
    assert model_path.is_file() and voices_path.is_file()


@pytest.mark.asyncio
async def test_synthesize_runs_kokoro_and_returns_mp3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)
    fake = _FakeKokoro()
    voice = Voice(id="af_sarah", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)

    with patch.object(provider, "_session", return_value=fake):
        payload = await provider.synthesize("Hola mundo", voice, Emotion.NEUTRAL)

    assert len(payload) > 0
    segment = AudioSegment.from_file(io.BytesIO(payload), format="mp3")
    assert abs(len(segment) - 500) < 150

    assert fake.calls[0]["text"] == "Hola mundo"
    assert fake.calls[0]["voice"] == "af_sarah"
    assert fake.calls[0]["lang"] == "en-us"
    assert fake.calls[0]["speed"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_synthesize_applies_emotion_rate_and_clamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)
    voice = Voice(id="af_sarah", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)

    happy = _FakeKokoro()
    with patch.object(provider, "_session", return_value=happy):
        await provider.synthesize("yay", voice, Emotion.HAPPY)
    assert happy.calls[0]["speed"] == pytest.approx(1.10)

    fast = _FakeKokoro()
    with patch.object(provider, "_session", return_value=fast):
        await provider.synthesize("go", voice, Emotion.ANGRY, rate=1.9)
    assert fast.calls[0]["speed"] == pytest.approx(2.0)  # clamped


@pytest.mark.asyncio
async def test_synthesize_uses_a_single_loaded_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model is loaded once and reused, not rebuilt per paragraph."""
    provider = _provider_with_pack(tmp_path, monkeypatch)
    fake = _FakeKokoro()
    voice = Voice(id="af_sarah", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)

    with patch.dict(sys.modules, {"kokoro_onnx": MagicMock(Kokoro=MagicMock(return_value=fake))}):
        await provider.synthesize("one", voice, Emotion.NEUTRAL)
        await provider.synthesize("two", voice, Emotion.NEUTRAL)
        cast(Any, sys.modules["kokoro_onnx"]).Kokoro.assert_called_once()

    assert [call["text"] for call in fake.calls] == ["one", "two"]


@pytest.mark.asyncio
async def test_synthesize_rejects_an_unknown_voice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)
    voice = Voice(id="af_nobody", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)

    with pytest.raises(ValueError, match="Unknown Kokoro voice"):
        await provider.synthesize("hi", voice, Emotion.NEUTRAL)


@pytest.mark.asyncio
async def test_synthesize_explains_a_missing_kokoro_onnx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)
    voice = Voice(id="af_sarah", locale="en_US", gender=GenderHint.FEMALE, age=AgeHint.ADULT)

    with (
        patch.dict(sys.modules, {"kokoro_onnx": None}),
        pytest.raises(RuntimeError, match="kokoro-onnx is not installed"),
    ):
        await provider.synthesize("hi", voice, Emotion.NEUTRAL)
    assert "audiobard[kokoro]" in INSTALL_HINT


@pytest.mark.asyncio
async def test_synthesize_maps_the_locale_to_the_kokoro_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider_with_pack(tmp_path, monkeypatch)
    fake = _FakeKokoro()
    voice = Voice(id="bm_george", locale="en_GB", gender=GenderHint.MALE, age=AgeHint.ADULT)

    with patch.object(provider, "_session", return_value=fake):
        await provider.synthesize("hello", voice, Emotion.NEUTRAL)

    assert fake.calls[0]["lang"] == "en-gb"


def test_supported_locales_are_unique_and_cover_the_pack() -> None:
    prefixes = [prefix for prefix, _lang in KOKORO_LOCALES.values()]
    assert len(set(prefixes)) == len(prefixes)
    assert all(len(prefix) == 1 and lang for prefix, lang in KOKORO_LOCALES.values())
    for locale in KOKORO_LOCALES:
        assert locale.count("_") == 1
    for voice in _PACK_VOICES:
        assert locale_for_voice(voice) in KOKORO_LOCALES


def test_cli_lists_kokoro_voices_from_the_local_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``audiobard voices --provider kokoro`` works from the local voice pack."""
    monkeypatch.setenv(VOICES_ENV_VAR, str(_write_voice_pack(tmp_path / "voices.bin")))
    monkeypatch.setenv(MODEL_ENV_VAR, str(_write_dummy_model(tmp_path / "model.onnx")))
    monkeypatch.setenv("AUDIOBARD_CACHE_DIR", str(tmp_path / "cache"))

    result = runner.invoke(
        app, ["voices", "--provider", "kokoro", "--locale", "en_US"]
    )

    assert result.exit_code == 0, result.output
    assert "af_sarah" in result.output
    assert "Voice ID" in result.output
