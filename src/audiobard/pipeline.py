"""Audiobook generation pipeline orchestrator."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from pathlib import Path

from pydub import AudioSegment
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from audiobard.audio.processor import AudioClip, AudioProcessor, ChapterMarker
from audiobard.config import AudioBardConfig
from audiobard.llm import GeminiClient, LLMClient, OllamaClient, OpenRouterClient
from audiobard.models import (
    CharactersResult,
    Emotion,
    Paragraph,
    VoiceAssignment,
)
from audiobard.parser import EpubParser, TextParser
from audiobard.parser.base import BookParser
from audiobard.persistence import PersistenceManager
from audiobard.tts import VoiceMapper
from audiobard.tts.base import EMOTION_PROSODY, TTSProvider
from audiobard.tts.edge_provider import EdgeProvider
from audiobard.tts.piper_provider import PiperProvider

logger = logging.getLogger(__name__)


def create_llm_client(config: AudioBardConfig) -> LLMClient:
    """Factory to create the configured LLM client."""
    if config.llm_provider == "ollama":
        return OllamaClient(
            model=config.llm_model,
            base_url=config.llm_base_url,
            temperature=config.llm_temperature,
            max_retries=config.llm_max_retries,
        )
    elif config.llm_provider == "gemini":
        return GeminiClient(
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_retries=config.llm_max_retries,
        )
    elif config.llm_provider == "openrouter":
        return OpenRouterClient(
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_retries=config.llm_max_retries,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {config.llm_provider}")


def create_tts_provider(config: AudioBardConfig) -> TTSProvider:
    """Factory to create the configured TTS provider."""
    if config.tts_provider == "piper":
        return PiperProvider(config)
    elif config.tts_provider == "edge":
        return EdgeProvider(config)
    else:
        raise ValueError(f"Unknown TTS provider: {config.tts_provider}")


def chunk_paragraphs(
    paragraphs: list[Paragraph], chunk_size: int = 1500
) -> list[list[Paragraph]]:
    """Group paragraphs into chunks of *chunk_size* words."""
    chunks = []
    current_chunk: list[Paragraph] = []
    current_words = 0
    for p in paragraphs:
        word_count = len(p.text.split())
        if current_words + word_count > chunk_size and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [p]
            current_words = word_count
        else:
            current_chunk.append(p)
            current_words += word_count
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


class AudioBookPipeline:
    """Coordinates parsing, character extraction, voice mapping, synthesis, and assembly."""

    def __init__(self, config: AudioBardConfig) -> None:
        self.config = config
        self.persistence = PersistenceManager(config.db_path)
        self.llm_client = create_llm_client(config)
        self.tts_provider = create_tts_provider(config)
        self.audio_processor = AudioProcessor()
        self.cache_dir = config.cache_dir / "pipeline"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Set LLM concurrency semaphore
        self._llm_semaphore = asyncio.Semaphore(config.llm_semaphore)

    async def run(
        self,
        book_path: Path,
        output_path: Path,
        resume: bool = True,
        dry_run: bool = False,
    ) -> None:
        """Run the complete pipeline from book file to finished audio file."""
        if not book_path.exists():  # noqa: ASYNC240
            raise FileNotFoundError(f"Book file not found: {book_path}")

        # Choose correct parser
        parser: BookParser = (
            EpubParser() if book_path.suffix.lower() == ".epub" else TextParser()
        )

        logger.info("Parsing book: %s", book_path)
        paragraphs = parser.parse(book_path)
        stats = parser.stats()
        title = getattr(parser, "title", None) or book_path.stem

        book_id = self.persistence.get_or_create_book(book_path, title, stats)

        if not resume:
            self.persistence.clear_checkpoints(book_id)

        # 1. Characters Extraction
        logger.info("Running character extraction...")
        checkpoint = self.persistence.get_checkpoint(book_id, "characters")
        if resume and checkpoint and checkpoint["status"] == "completed":
            characters = self.persistence.get_characters(book_id)
            logger.info("Loaded %d characters from checkpoint", len(characters))
        else:
            # Construct a text sample from the first few paragraphs (~5000 words max)
            sample_paragraphs = []
            word_count = 0
            for p in paragraphs:
                p_words = len(p.text.split())
                if word_count + p_words > 5000:
                    break
                sample_paragraphs.append(p.text)
                word_count += p_words

            sample_text = "\n\n".join(sample_paragraphs)
            async with self._llm_semaphore:
                char_result = await self.llm_client.extract_characters(sample_text)

            characters = char_result.characters
            self.persistence.save_characters(book_id, characters)
            self.persistence.save_checkpoint(book_id, "characters", "completed", {})
            logger.info("Extracted %d characters", len(characters))

        # 2. Voice Assignment
        logger.info("Mapping voices...")
        checkpoint = self.persistence.get_checkpoint(book_id, "voice_assignment")
        if resume and checkpoint and checkpoint["status"] == "completed":
            voice_assignments = self.persistence.get_voice_mapping(book_id)
            logger.info("Loaded voice mappings from checkpoint")
        else:
            voices = await self.tts_provider.list_voices(self.config.tts_locale)
            if not voices:
                raise RuntimeError(
                    f"No voices found for locale: {self.config.tts_locale}"
                )
            voices_path = self.config.voices_dir / f"{self.config.tts_locale}.json"
            mapper = VoiceMapper(voices_path)
            voice_assignments = list(mapper.assign_all(characters).values())
            self.persistence.save_voice_mapping(book_id, voice_assignments)
            self.persistence.save_checkpoint(book_id, "voice_assignment", "completed", {})
            logger.info("Mapped %d speakers to voices", len(voice_assignments))

        # Get voice lookup map
        voices = await self.tts_provider.list_voices(self.config.tts_locale)
        voice_map = {v.id: v for v in voices}

        # 3. Attribution & Synthesis
        chunks = chunk_paragraphs(paragraphs, chunk_size=self.config.chunk_words)
        logger.info("Split book into %d chunks for synthesis", len(chunks))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Processing chunks...", total=len(chunks))

            for idx, chunk in enumerate(chunks):
                checkpoint_name = f"chunk_{idx}"
                checkpoint = self.persistence.get_checkpoint(book_id, checkpoint_name)

                if resume and checkpoint and checkpoint["status"] == "completed":
                    progress.update(task, advance=1)
                    continue

                # Run dialog attribution on chunk text
                chunk_text = "\n\n".join([p.text for p in chunk])
                async with self._llm_semaphore:
                    attr_result = await self.llm_client.attribute_dialog(
                        chunk_text, CharactersResult(characters=characters)
                    )

                # Match attributed dialog lines back to paragraphs sequentially
                dialog_lines = attr_result.lines
                dl_idx = 0
                assigned_paragraphs: list[tuple[Paragraph, str, Emotion]] = []

                for p in chunk:
                    if p.is_dialog and dl_idx < len(dialog_lines):
                        dl = dialog_lines[dl_idx]
                        assigned_paragraphs.append((p, dl.speaker, dl.emotion))
                        dl_idx += 1
                    else:
                        assigned_paragraphs.append((p, "Narrator", Emotion.NEUTRAL))

                # Synthesize paragraphs
                if not dry_run:
                    for p, speaker, emotion in assigned_paragraphs:
                        clip_file = self.cache_dir / f"clip_{book_id}_{p.index}.mp3"
                        meta_file = self.cache_dir / f"clip_{book_id}_{p.index}.json"

                        if clip_file.exists() and meta_file.exists():
                            continue

                        # Find voice assignment
                        va = next(
                            (x for x in voice_assignments if x.canonical_id == speaker),
                            None,
                        )
                        if not va:
                            va = next(
                                (x for x in voice_assignments if x.canonical_id == "Narrator"),
                                VoiceAssignment(
                                    canonical_id="Narrator", voice_id=voices[0].id
                                ),
                            )

                        voice = voice_map.get(va.voice_id, voices[0])

                        # Call TTS provider
                        mp3_bytes = await self.tts_provider.synthesize(
                            text=p.text,
                            voice=voice,
                            emotion=emotion,
                            rate=va.rate,
                            pitch=va.pitch,
                        )

                        # Calculate duration using pydub
                        segment = await asyncio.to_thread(
                            AudioSegment.from_file, io.BytesIO(mp3_bytes), format="mp3"
                        )
                        duration_ms = len(segment)

                        # Save audio and metadata
                        clip_file.write_bytes(mp3_bytes)
                        meta_file.write_text(
                            json.dumps(
                                {
                                    "speaker": speaker,
                                    "emotion": emotion.value,
                                    "duration_ms": duration_ms,
                                }
                            ),
                            encoding="utf-8",
                        )

                self.persistence.save_checkpoint(book_id, checkpoint_name, "completed", {})
                progress.update(task, advance=1)

        # 4. Assembly
        if dry_run:
            logger.info("Dry-run complete. Skipping audio assembly.")
            return

        logger.info("Assembling final audio file...")
        clips: list[AudioClip] = []
        chapters: list[ChapterMarker] = []
        current_time_ms = 0
        current_chapter_idx = -1
        chapter_start_ms = 0

        for p in paragraphs:
            clip_file = self.cache_dir / f"clip_{book_id}_{p.index}.mp3"
            meta_file = self.cache_dir / f"clip_{book_id}_{p.index}.json"

            if not clip_file.exists() or not meta_file.exists():
                raise FileNotFoundError(
                    f"Missing audio clip or metadata for paragraph index {p.index}"
                )

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            duration = int(meta["duration_ms"])
            emotion = Emotion(meta["emotion"])

            clips.append(
                AudioClip(
                    mp3_bytes=clip_file.read_bytes(),
                    speaker=meta["speaker"],
                    emotion=emotion,
                    duration_ms=duration,
                )
            )

            # Handle M4B chapter calculation
            pause_ms = EMOTION_PROSODY.get(emotion, {"pause_after_ms": 250})[
                "pause_after_ms"
            ]

            if p.chapter != current_chapter_idx:
                if current_chapter_idx != -1:
                    chapters.append(
                        ChapterMarker(
                            title=f"Chapter {current_chapter_idx + 1}",
                            start_ms=chapter_start_ms,
                            end_ms=current_time_ms,
                        )
                    )
                current_chapter_idx = p.chapter
                chapter_start_ms = current_time_ms

            current_time_ms += duration + int(pause_ms)

        if current_chapter_idx != -1:
            chapters.append(
                ChapterMarker(
                    title=f"Chapter {current_chapter_idx + 1}",
                    start_ms=chapter_start_ms,
                    end_ms=current_time_ms,
                )
            )

        # Merge all clips
        logger.info("Concatenating clips and applying normalization...")
        final_mp3_bytes = await self.audio_processor.concatenate(clips)

        # Export final output
        logger.info("Exporting finished audio to: %s", output_path)
        if output_path.suffix.lower() == ".m4b":
            await self.audio_processor.export_m4b(final_mp3_bytes, output_path, chapters)
        else:
            await self.audio_processor.export_mp3(final_mp3_bytes, output_path)

        logger.info("Audiobook generated successfully!")
