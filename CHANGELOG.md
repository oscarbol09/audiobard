# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The changelog is an entry point for humans: every PR that changes behavior
adds an entry under the relevant section, in the same commit as the change.

## [0.1.0] - 2026-08-20

### Added

- **Phase 1: Project Foundation & Book Parsers**:
  - `BookParser` ABC with concrete `TextParser` (plain text with Gutenberg header cleaning) and `EpubParser` (EPUB parsing using `ebooklib`).
  - `LLMClient` ABC with retries, exponential backoff, jitter, and Pydantic JSON schema generation.
  - LLM concrete providers: `OllamaClient` (offline), `GeminiClient` (Google Gemini REST), `OpenRouterClient`.
  - Versioned prompt infrastructure (`src/audiobard/llm/prompts.py`) protected against in-place edits.
  - Deterministic `VoiceMapper` scoring tone attributes with cosine similarity.
- **Phase 2: Pipeline Core (TTS & Audio)**:
  - `TTSProvider` ABC with in-memory LRU caching (500 MB limit) and disk caching.
  - `PiperProvider` wrapping local `piper` binary with automatic ONNX model downloads from Hugging Face and emotion-based prosody scaling.
  - `EdgeProvider` for cloud TTS via `edge-tts` with rate/pitch mapping.
  - `AudioProcessor` for concatenation, emotion pause insertion, `-16 dBFS` normalization in thread pools, and M4B/MP3 chapter export using FFmpeg `FFMETADATA1`.
  - `PersistenceManager` managing SQLite schemas for books, characters, voice assignments, checkpoints (`--resume`), and LLM caches.
  - `AudioBookPipeline` orchestrating parse → extract → map → attribute → synthesize → assemble.
  - CLI subcommands `generate`, `voices`, `validate-config`.
- **Phase 3: Quality, Caching & Benchmarking**:
  - SHA-256 request caching in `LLMClient._call_with_retry` backed by SQLite `llm_cache`.
  - Hand-labeled dialog attribution gold standard for *Pride and Prejudice* Chapter 3 (`eval/gold_standard/p_and_p_ch3.json`).
  - Attribution accuracy benchmark runner (`eval/benchmark.py`) computing accuracy and confusion matrices.
  - CLI subcommands `audiobard benchmark` and `audiobard stats`.
  - CI workflow (`.github/workflows/benchmark.yml`) for weekly attribution regression testing.
- **Phase 4: Documentation & Release**:
  - Developer guides `docs/prompt-engineering.md` and `docs/adding-a-provider.md`.
  - YAML and JSON config file loader support (`~/.config/audiobard/config.yaml`).
  - Security and hygiene guards (`tools/guards.py`).
  - 100+ unit test suite with >79% coverage.