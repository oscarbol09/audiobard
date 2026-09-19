<p align="center">
  <img src="assets/banner.svg" alt="AudioBard Banner" width="100%">
</p>

<p align="center">
  <a href="https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml"><img src="https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

---

AudioBard converts public-domain books (EPUB and TXT) into multi-voice audiobooks with distinct, consistent voices assigned to each character. It can run completely offline on local compute or via cloud API keys (BYOK).

## Motivation

Standard text-to-speech tools read entire books in a single monotone voice without distinguishing character dialogue from narrator descriptions. Commercial audio services often charge recurring monthly subscriptions or require uploading entire manuscripts to proprietary remote servers.

AudioBard provides a local-first alternative: it parses book structure, extracts speaking characters, attributes spoken lines with emotional context, and synthesizes audio tracks using neural TTS engines.

## Features

- **Character Extraction & Dialogue Attribution:** Identifies characters, aliases, and gender/age hints across chapters, then attributes spoken lines to the corresponding speaker.
- **Multi-Voice Neural Synthesis:** Assigns unique voice models from a tone-aware voice pool to each character.
- **Offline & Cloud Execution Modes:** Run entirely offline using [Ollama](https://ollama.com) and [Piper TTS](https://github.com/rhasspy/piper), or connect cloud providers (NVIDIA NIM, OpenRouter, Google Gemini, Edge TTS) using your own API keys.
- **Desktop GUI & CLI:** Includes a native desktop interface built with Tauri v2 and Vue 3 (with English and Spanish localization), as well as a standalone CLI for scripting.
- **Deterministic Mapping:** Persists character-to-voice mappings in SQLite to guarantee voice consistency across chapters and runs.

<p align="center">
  <img src="assets/demo-pipeline.svg" alt="AudioBard Pipeline Architecture" width="900">
</p>

## Comparison with Alternatives

| Feature | AudioBard | Commercial Cloud Platforms | Standard Reader TTS |
| :--- | :--- | :--- | :--- |
| **Execution Environment** | Local offline or Cloud BYOK | Cloud-hosted servers | Local device |
| **Character Casting** | Multi-voice per character | Manual studio configuration | Single narrator voice |
| **Interfaces** | Desktop GUI (Tauri) + CLI | Web dashboard only | Desktop or browser extension |
| **Licensing & Cost** | Open source (MIT), zero subscription fees | Subscription ($15–$100+/mo) | Free or bundled |
| **Attribution Verification** | Hermetic benchmark suite vs gold standard | Not published | Not applicable |

## Quickstart

### Prerequisites

- **Python 3.10+**
- **FFmpeg** on system `PATH` (for audio assembly and normalization)
- *(Optional)* **Ollama** and **Piper TTS** for local offline synthesis
- *(Optional)* **Rust 1.77+** and **Node.js 18+** if building the Desktop GUI from source

### Desktop GUI Application (Tauri v2 + Vue 3)

```bash
# Clone the repository
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard

# Install Python dependencies with local and cloud provider extras
pip install -e ".[dev,llm-gemini,llm-ollama,tts-piper]"

# Launch the Desktop GUI
cargo tauri dev
```

### Command Line Interface (CLI)

```bash
# Generate a complete audiobook from an EPUB file
audiobard generate book.epub --output audiobook.mp3

# Dry-run mode: parse text and attribute dialogue without synthesizing audio
audiobard generate book.epub --dry-run

# Run system and dependency diagnostics
audiobard doctor

# List available voices for a specific locale
audiobard voices --locale en_US
```

## Companion Tools

### [PDF2Bard](https://github.com/oscarbol09/pdf2bard) — PDF to EPUB Converter

AudioBard natively parses **EPUB** and **TXT** files. If your book is in PDF format, use our companion pre-processor:

[**PDF2Bard (`oscarbol09/pdf2bard`)**](https://github.com/oscarbol09/pdf2bard)

- **Paragraph Reflow:** Unwraps margin-bound line breaks while preserving legitimate dialogue turns.
- **De-Hyphenation:** Reconstructs split words across lines without damaging compound terms.
- **Header & Footer Stripping:** Detects and removes running headers, footers, and page numbers.
- **Dialogue Normalization:** Standardizes quotation marks (`—`, `«»`, `"`) for accurate attribution.

## Command Reference

| Command | Description |
| :--- | :--- |
| `cargo tauri dev` | Launch the Desktop GUI in development mode |
| `cargo tauri build` | Compile standalone desktop installers (`.exe`, `.msi`, `.dmg`, `.AppImage`) |
| `audiobard generate <book> -o <out>` | Run end-to-end pipeline: parse, attribute, synthesize, assemble |
| `audiobard generate <book> --dry-run` | Run parsing and dialogue attribution without TTS synthesis |
| `audiobard doctor` | Verify dependencies, FFmpeg, Piper, Ollama, API keys, and cache |
| `audiobard benchmark --llm <provider>` | Run attribution accuracy scoring against the gold standard dataset |
| `audiobard stats` | Display cache hit rates, processed books, and storage usage |
| `audiobard voices --locale <loc>` | List available TTS voice models for a locale (e.g. `en_US`, `es_ES`) |
| `audiobard validate-config` | Validate configuration files, active providers, and safety guardrails |

## Repository Structure

```text
audiobard/
├── src/audiobard/
│   ├── cli.py                    # CLI entry point (Typer application)
│   ├── config.py                 # Pydantic configuration settings
│   ├── doctor.py                 # System and environment diagnostics
│   ├── parser/                   # TXT and EPUB parsers (BookParser ABC)
│   ├── llm/                      # LLM clients (LLMClient ABC) and versioned prompts
│   ├── tts/                      # TTS providers (TTSProvider ABC) and voice mapper
│   ├── audio/                    # Audio assembly, volume normalization (FFmpeg/pydub)
│   ├── pipeline.py               # Core pipeline orchestrator
│   └── persistence.py            # SQLite state: character rosters, voice mapping, cache
├── gui/                          # Vue 3 + Tailwind CSS desktop frontend
├── src-tauri/                    # Tauri v2 desktop application wrapper
├── tests/                        # Automated test suite (342 unit & integration tests)
├── eval/
│   ├── gold_standard/            # Hand-labeled dialogue ground truth datasets
│   └── benchmark.py              # Attribution accuracy benchmark runner
├── data/
│   ├── books/                    # Public-domain sample books (gitignored)
│   └── voices/                   # Regional voice catalog metadata (en_US, es_MX, es_CO, es_ES)
├── tools/
│   ├── guards.py                 # Supply-chain and data hygiene contract guards
│   └── lint_skills.py            # Prompt and skills linter
└── docs/                         # Documentation site and provider guides
```

## Architecture & Pipeline

The `generate` command coordinates six decoupled stages:

1. **Ingest & Parse:** Extracts chapters and paragraphs from `.epub` or `.txt`, stripping Project Gutenberg headers and footers.
2. **Character Extraction:** Analyzes opening chapters to extract canonical character IDs, aliases, and demographic/tone hints.
3. **Voice Mapping:** Selects suitable voice models from regional pools based on gender, age, and tone similarity, with deterministic hash tie-breaking.
4. **Dialogue Attribution:** Processes sliding text windows (~1,500 words) to assign each sentence to a character or the Narrator, along with emotional context.
5. **TTS Synthesis:** Synthesizes individual lines with emotion-informed prosody parameters, utilizing persistent disk and memory caches.
6. **Mastering & Assembly:** Normalizes loudness, injects configurable pacing gaps, and packages the result into `.mp3` or chapter-tagged `.m4b`.

## Extension Model

Providers are decoupled through abstract interfaces:

```yaml
# config.yaml
llm:
  provider: ollama        # ollama | gemini | openrouter | nim
  model: qwen2.5:7b
tts:
  provider: piper         # piper | edge
  locale: en_US
```

- **`LLMClient`:** `ollama_client` (local default), `gemini_client` (cloud), `openrouter_client` (cloud), `nim_client` (NVIDIA NIM).
- **`TTSProvider`:** `piper_provider` (local neural default), `edge_provider` (cloud).
- **`BookParser`:** `text_parser`, `epub_parser`.

To add a new provider, subclass `LLMClient` or `TTSProvider`, implement the abstract methods, and register the provider in the corresponding module factory. See [docs/guides/adding-a-provider.md](docs/guides/adding-a-provider.md).

## Contributing

Please review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting pull requests.

Verification gate required for all contributions:

```bash
ruff check src tests tools
mypy src/audiobard
pytest --cov=audiobard --cov-fail-under=90 -m "not integration"
python tools/guards.py
```

## Ethics & Legal Disclaimer

AudioBard is designed for public-domain works (e.g. Project Gutenberg, LibriVox, Standard Ebooks). Users are responsible for verifying the copyright status of any input material.

- Unauthorized voice cloning, DRM circumvention, and bulk generation for spam are prohibited.
- This software is distributed under the MIT License — see [LICENSE](LICENSE).

## License

MIT License — see [LICENSE](LICENSE). Gold standard datasets in `eval/gold_standard/` are dedicated to the public domain under CC0.