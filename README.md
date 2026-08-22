<p align="center">
  <img src="assets/mascot/audiobard_logo.svg" alt="AudioBard" width="160">
</p>

# AudioBard

*The audiobook generator that reads for you.*

[![CI](https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml/badge.svg)](https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/oscarmb09)

An open-source audiobook generator that turns public-domain classics into narrated audiobooks with **distinct voices per character** — 100% free either way, and offline-capable if you want zero cloud dependency.

It parses a book (**TXT or EPUB only** — no PDF yet, see below), detects who speaks each line with an LLM, assigns a consistent voice to every character, and synthesizes natural-sounding audio with a neural TTS engine. Both the LLM and the TTS engine are swappable between a local, fully offline provider and a free cloud API — see [Prerequisites](#prerequisites).

> **Why I built this.**
>
> Reading is a joy; finding the time is not. I wanted a tool that reads a book *to* me the way I would read it aloud myself — with different voices for different characters, and no cloud dependency deciding whether the project works today. Everything here runs on your own machine, and it costs nothing.

## Demo

<!-- [YOUR_SAMPLE]: drop a short (10–20s) generated clip here once you have one — e.g. a link to a hosted MP3, or a GIF of the CLI running end-to-end. A sample sells the multi-voice pitch far faster than prose does. -->

## Status & Capabilities

**Status: ✅ v0.1.0-MVP Ready.** All core pipeline capabilities across text/EPUB parsing, LLM-based dialog attribution, voice mapping, neural TTS synthesis with Piper/Edge, SQLite persistence, and attribution benchmarking are fully implemented and verified.

## What this is

A structured pipeline that turns plain text into a multi-voice audiobook:

```
parse ──► extract characters ──► assign voices ──► attribute dialog ──► synthesize ──► assemble
  │           (LLM)                 (tone-aware)      (LLM, chunked)      (TTS)           (audio)
  v               v                     v                    v                v               v
TXT/EPUB     Who's in the          Unique voice       Who says each      Per-line        MP3 / M4B
→ paragraphs  book? Canonical       per character,     line, with         speech,          with
              IDs + aliases         filtered by        emotion           async,           chapter
                                    gender/age/tone                                        metadata
```

The core pipeline is **provider-agnostic**: every external dependency (LLM, TTS) sits behind a small interface. Run it fully offline with [Ollama](https://ollama.com) + [Piper](https://github.com/rhasspy/piper) if you have the hardware, or fully via free cloud APIs (OpenRouter, Gemini, Edge TTS) if you don't — see [Extension model](#extension-model).

**Supported input: TXT and EPUB only — no PDF.** This was a deliberate scope decision (see the dev plan's tech-stack notes): OCR quality on scanned classics is poor and would quietly wreck dialog attribution, while EPUB already ships clean chapter/paragraph structure. If you have a PDF, convert it to EPUB or TXT first — [Calibre](https://calibre-ebook.com) does this for free. **PDF support is a welcome contribution** if someone wants to tackle a solid extraction path (e.g. `pdfplumber` + layout-aware chapter detection) behind the same `BookParser` interface as `TextParser`/`EpubParser` — see [Extension model](#extension-model) and [Contributing](#contributing).

## Prerequisites

- **Python 3.10+** — required either way.
- **[ffmpeg](https://ffmpeg.org/download.html)** — required either way (audio assembly).

Pick one LLM path and one TTS path; they're independent, so you can mix (e.g. cloud LLM + local TTS):

| | Local (offline, $0, no account) | Cloud (API, $0 free tier, no local compute) |
|---|---|---|
| **LLM** | [Ollama](https://ollama.com) running (`ollama serve`) with a model: `ollama pull qwen2.5:7b` | `AUDIOBARD_LLM_PROVIDER=openrouter` or `gemini` + an API key (see below) |
| **TTS** | [Piper](https://github.com/rhasspy/piper/releases) binary on `PATH` (lightweight, CPU-only — models auto-download on first use) | `AUDIOBARD_TTS_PROVIDER=edge` (Microsoft Edge TTS, no API key, no SLA) |

**If your machine can't comfortably run a local 7B model** (no GPU, limited RAM), the cloud path needs nothing more than Python — no local model download at all. A working `.env` for a fully cloud-based, zero-local-compute setup:

```bash
AUDIOBARD_LLM_PROVIDER=openrouter
AUDIOBARD_LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free   # any OpenRouter :free model ID works
OPENROUTER_API_KEY=your_key_here
AUDIOBARD_TTS_PROVIDER=edge
```

There's no dedicated NVIDIA client — OpenRouter's catalog includes NVIDIA-hosted free-tier models, so pointing `AUDIOBARD_LLM_MODEL` at one gets you NVIDIA inference through the existing `openrouter` provider, no code changes needed. [Gemini's free tier](https://ai.google.dev) works the same way via `AUDIOBARD_LLM_PROVIDER=gemini` + `GEMINI_API_KEY`.

**Note:** cloud free tiers are non-commercial only (see [Extension model](#extension-model) and [SECURITY.md](SECURITY.md)); free-tier model availability rotates over time, so check [openrouter.ai/models](https://openrouter.ai/models) for what's currently live.

## Quick start

```bash
# Clone and install dependencies
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard

# Local path (Ollama + Piper):
pip install -e ".[dev,llm-ollama,tts-piper]"

# Cloud path (OpenRouter/Gemini + Edge TTS) — openrouter and edge-tts need no extras,
# they're core dependencies already:
pip install -e ".[dev,llm-gemini]"   # omit llm-gemini too if you're only using openrouter

# Generate an audiobook
audiobard generate book.epub --output audiobook.mp3

# Or run a dry-run to test character extraction and dialog attribution without synthesis
audiobard generate book.epub --dry-run
```

## Command reference

| Command | What it does |
|---|---|
| `audiobard generate <book> -o <out>` | Full pipeline: parse → attribute → synthesize → assemble |
| `audiobard generate <book> --dry-run` | Parse + LLM attribution only — no synthesis (fast prompt iteration) |
| `audiobard benchmark --llm <provider>` | Attribution accuracy against the gold standard (see [eval/README.md](eval/README.md)) |
| `audiobard stats` | Cache hit rate, books processed, and disk cache usage |
| `audiobard voices --locale en_US` | List available TTS voices for a locale |
| `audiobard validate-config` | Check config, providers, and ethics guardrails |

## File structure

```
audiobard/
├── src/audiobard/
│   ├── cli.py                    # CLI entry point
│   ├── config.py                 # Pydantic settings
│   ├── parser/                   # TXT/EPUB parsers (BookParser ABC)
│   ├── llm/                      # LLM clients (LLMClient ABC) + versioned prompts
│   ├── tts/                      # TTS providers (TTSProvider ABC) + voice mapper
│   ├── audio/                    # Audio assembly (pydub/ffmpeg)
│   ├── pipeline.py               # Orchestrator
│   └── persistence.py            # SQLite: speakers, voices, cache, runs
├── tests/                        # pytest suite (unit + integration)
├── eval/
│   ├── gold_standard/            # Hand-labeled dialog attribution (immutable)
│   └── benchmark.py              # Accuracy scorer
├── data/
│   └── books/                    # Sample books (gitignored — public domain only)
├── tools/
│   ├── guards.py                 # Security guards run by CI
│   └── lint_skills.py            # (planned) prompt/skill linting
├── .github/workflows/            # CI, benchmark, notifications
├── AudioBard_DevPlan.md          # Full development plan (phases, costs, ethics)
└── docs/                         # Provider and prompt-engineering guides
```

## How it works

The `generate` command runs the pipeline above:

1. **Parse** — TXT/EPUB → paragraphs with chapter and line metadata; Project Gutenberg headers/footers stripped.
2. **Extract characters** *(LLM)* — the LLM returns canonical IDs (`Character_A`, …), aliases, tone, and gender/age hints, validated against a Pydantic schema.
3. **Assign voices** — voices are chosen from a **tone-aware pool**: filtered by gender/age first, scored by tone similarity, with a deterministic hash tie-break so the same book always maps to the same voices.
4. **Attribute dialog** *(LLM, chunked)* — every line gets a speaker + emotion; chunks of ~1500 words with a 5-paragraph sliding window resolve ambiguous attribution; results validated by Pydantic (drop-and-retry on schema mismatch).
5. **Synthesize** *(TTS, async)* — per-line speech with emotion→prosody mapping (rate/pitch/pause), local disk cache keyed by `(text, voice, emotion)`.
6. **Assemble** — clips joined with configurable silence gaps, volume normalized, exported as MP3 or M4B with chapter metadata. CPU-bound audio work runs in a thread pool; the LLM/TTS I/O is fully async.

Two properties make the output trustworthy:

- **Voice consistency across chapters** — the speaker↔voice mapping is persisted in SQLite (`book_id + canonical_id`), so a character never changes voice between chapters, and never gets re-assigned.
- **No fabricated speech** — the LLM may only output speaker IDs from the canonical character list extracted in step 2; anything else is retried, then rejected.

## Extension model

External dependencies are pluggable by design, with zero code changes — just config:

```yaml
# config.yaml
llm:
  provider: ollama        # ollama | gemini | openrouter
  model: qwen2.5:7b
tts:
  provider: piper         # piper | edge
  locale: en_US
```

- **`LLMClient`** — `ollama_client` (offline, primary), `gemini_client` (opt-in cloud, native JSON mode), `openrouter_client` (opt-in fallback).
- **`TTSProvider`** — `piper_provider` (offline, primary), `edge_provider` (opt-in cloud; note it has no SLA — see [SECURITY.md](SECURITY.md)).
- **`BookParser`** — `text_parser`, `epub_parser`.

Adding a provider = one class in one file + one config example + tests. See [docs/adding-a-provider.md](docs/adding-a-provider.md) for the walkthrough and [docs/prompt-engineering.md](docs/prompt-engineering.md) for how the versioned LLM prompts are structured and tuned.

## Contributing

Thinking about a PR? Read [CONTRIBUTING.md](CONTRIBUTING.md) first — it states the one rule everything follows from, what gets merged, what gets declined, and why. All contributions are governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

**Quick orientation for new contributors:** the repo ships labeled issues — [`good first issue`](https://github.com/oscarbol09/audiobard/labels/good%20first%20issue) for onboarding, [`help wanted`](https://github.com/oscarbol09/audiobard/labels/help%20wanted) for meatier tasks, and [`ethics-review`](https://github.com/oscarbol09/audiobard/labels/ethics-review) for features that touch identity or consent.

## Ethics & responsible use

AudioBard converts public-domain text to audio. The following are explicitly out of scope, and require an `ethics-review` RFC before any implementation PR is accepted: voice cloning without consent, DRM circumvention, impersonation/deepfakes, and bulk generation for spam. Full policy in the [development plan, §10](AudioBard_DevPlan.md) and the [ethics-review issue](https://github.com/oscarbol09/audiobard/issues/7).

## Copyright & legal disclaimer

**AudioBard is designed exclusively for public-domain works** (e.g., Project Gutenberg, LibriVox, Standard Ebooks). The user is solely responsible for verifying the copyright status of any text before processing it.

- This software does not validate, enforce, or assume copyright ownership of input material.
- Generating audiobooks from copyrighted works without authorization may infringe the rights of authors, publishers, and voice artists.
- The tool is provided "as is" under the MIT License — see [LICENSE](LICENSE). The authors disclaim all warranties and liability for how the software is used, including any copyright infringement by end users.
- No warranty of fitness for a particular purpose, non-infringement, or merchantability is implied.

If you are a rights holder and believe this software is being used to infringe your copyright, please follow standard DMCA/notice-and-takedown procedures with the hosting platform.

## License

MIT — see [LICENSE](LICENSE). The gold standard dataset (`eval/gold_standard/`) is CC0.