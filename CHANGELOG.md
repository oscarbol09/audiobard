# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The changelog is an entry point for humans: every PR that changes behavior
adds an entry under the relevant section, in the same commit as the change.

## [0.2.0] - 2026-08-26

### Added

- **Desktop GUI (Tauri v2 + Vue 3 + Tailwind CSS)**:
  - Native cross-platform desktop application interface for AudioBard.
  - Drag-and-drop book uploader (`UploadSection.vue`) supporting `.epub` and `.txt`.
  - Live progress feedback (`GenerationProgress.vue`) polling synthesis updates.
  - Audiobook Library panel (`LibraryPanel.vue`) with search, audio playback, and book regeneration.
  - Native folder browser command (`select_output_folder`) and cache cleanup command (`clear_cache`).
  - Automatic Python FastAPI sidecar lifecycle management with health check and dev mode fallback.
  - Responsive Light, Dark, and System appearance theme modes.
  - Incomplete audio filtering toggle and local timezone date formatting in library.
- **Free vs Premium Model Filter & Expanded Live Catalog**:
  - Filter toggle buttons (`Todos` / `⭐ Gratis (Free)` / `💎 Prémium (Pago)`) in main screen and Settings modal.
  - Comprehensive model catalog across OpenRouter (NVIDIA Nemotron 3 Ultra/Super, MiniMax M3/M2.7, Gemma 4 31B/26B, Z.ai GLM 5.2, Claude 3.5 Sonnet, GPT-4o, DeepSeek R1), NVIDIA NIM, Google Gemini, and Ollama.
- **BYOK (Bring Your Own Key) & Cloud Providers**:
  - Dedicated `NimClient` (`src/audiobard/llm/nim_client.py`) for NVIDIA Inference Microservices (`https://integrate.api.nvidia.com/v1/chat/completions`).
  - Dynamic BYOK configuration fields in GUI Settings Modal for NVIDIA NIM, OpenRouter, Google Gemini, and Ollama.
  - Support for `AUDIOBARD_NVIDIA_NIM_API_KEY`, `NVIDIA_NIM_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`.
- **Narrator Gender Deduction & Regional Voice Pools**:
  - Contextual gender detection for first-person narrators (e.g. *Noches Blancas*) in `VoiceMapper`.
  - Dedicated Latin American Spanish (`es_MX`) and Colombian Spanish (`es_CO`) voice catalogs with automatic Edge TTS voice pairing.
- **Environment Diagnostics (`audiobard doctor`)**:
  - CLI diagnostic command collecting OS details, Python runtime, FFmpeg, Piper, Ollama connectivity, cache size, and redacted API keys (contributed via PR #68).
- **FFmpeg Discovery & M4B Error Handling**:
  - Multi-location binary resolver (`find_ffmpeg`) searching env vars, system PATH, `imageio_ffmpeg`, and local `tools/` subdirectories.
  - User-friendly error message on missing FFmpeg during M4B chapter export (contributed via PR #72).
- **GUI Multi-Language Support (i18n)**:
  - Pinia store `useI18nStore` (`gui/src/stores/i18n.ts`) providing full reactive internationalization.
  - Instant language switcher in Settings modal supporting **Spanish (🇪🇸)** and **English (🇺🇸)** across all components.

### Fixed

- Fixed `audiobard` console script entry point in `pyproject.toml` (`audiobard.cli:app`).
- Added resilient pre-validation normalizer for creative LLM emotion labels (e.g. `impatient` -> `angry`) and character metadata.
- Fast-fail HTTP client on non-retriable status codes (400, 401, 403, 404, 410).
- Voice assignment cache invalidation when switching TTS engine on pipeline resume.
- Dialog count mismatch validation preventing attribution index drift.

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