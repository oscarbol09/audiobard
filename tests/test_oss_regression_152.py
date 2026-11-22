"""Regression for punctuation-only paragraphs (#152)."""

import asyncio
import io
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from edge_tts.exceptions import NoAudioReceived
from pydub import AudioSegment
from pydub.generators import Sine

from audiobard.config import AudioBardConfig
from audiobard.models import AttributionResult, CharactersResult
from audiobard.pipeline import AudioBookPipeline


@pytest.mark.asyncio
async def test_edge_scene_dividers_render_as_silent_clips(tmp_path: Path) -> None:
    book_path = tmp_path / "book.txt"
    opening, ending = "The first scene ends.", "A new scene begins…"
    dividers = ("* * *", "— …")
    text = "\n\n".join((opening, *dividers, ending))
    await asyncio.to_thread(book_path.write_text, text, encoding="utf-8")

    sample = io.BytesIO()
    tone = Sine(440, sample_rate=24000).to_audio_segment(duration=100)
    await asyncio.to_thread(tone.export, sample, format="mp3")
    speech_mp3 = sample.getvalue()

    def communicate(text: str, **_options: str) -> SimpleNamespace:
        async def stream() -> AsyncIterator[dict[str, str | bytes]]:
            if text in dividers:
                raise NoAudioReceived("No audio was received")
            yield {"type": "audio", "data": speech_mp3}

        return SimpleNamespace(stream=stream)

    config = AudioBardConfig(
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "test.db",
        voices_dir=tmp_path / "voices",
        tts_provider="edge",
        tts_locale="en_US",
    )
    voices = [{"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"}]
    llm = AsyncMock()
    llm.extract_characters.return_value = CharactersResult(characters=[])
    llm.attribute_dialog.return_value = AttributionResult(lines=[])
    output = tmp_path / "book.mp3"
    with (
        patch("audiobard.pipeline.create_llm_client", return_value=llm),
        patch("edge_tts.list_voices", new=AsyncMock(return_value=voices)),
        patch("edge_tts.Communicate", side_effect=communicate) as edge_request,
    ):
        pipeline = AudioBookPipeline(config)
        try:
            await pipeline.run(book_path, output)
        except RuntimeError as exc:
            if isinstance(exc.__cause__, NoAudioReceived):
                raise AssertionError("A scene divider aborted audiobook synthesis") from exc
            raise

    assert sorted(call.kwargs["text"] for call in edge_request.call_args_list) == [ending, opening]
    clips = sorted(pipeline.cache_dir.glob("clip_*.mp3"))
    assert len(clips) == 4
    for path in clips[1:3]:
        clip = await asyncio.to_thread(AudioSegment.from_file, str(path), format="mp3")
        assert len(clip) == pytest.approx(500, abs=1)
        assert clip.rms == 0
    assert await asyncio.to_thread(output.is_file)
