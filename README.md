<p align="center">
  <img src="assets/mascot/audiobard_logo.svg" alt="AudioBard" width="160">
</p>

# AudioBard

*The audiobook generator that reads for you.*

[![CI](https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml/badge.svg)](https://github.com/oscarbol09/audiobard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An open-source audiobook generator that turns public-domain classics into narrated audiobooks with **distinct voices per character** — entirely offline, entirely free, no API keys required.

It parses a book (TXT/EPUB), detects who speaks each line with a local LLM, assigns a consistent voice to every character, and synthesizes natural-sounding audio with a local neural TTS engine.

> **Why I built this.** <!-- [YOUR_STORY]: a couple of honest sentences about why this project exists — what you were trying to do when it didn't exist. The projects people trust are the ones that say why they were built. -->
>
> Reading is a joy; finding the time is not. I wanted a tool that reads a book *to* me the way I would read it aloud myself — with different voices for different characters, and no cloud dependency deciding whether the project works today. Everything here runs on your own machine, and it costs nothing.

## Does it actually work?

**Status: 🚧 Pre-MVP.** The architecture and development plan are published ([`AudioBard_DevPlan.md`](AudioBard_DevPlan.md)); the implementation starts with Phase 1. Everything below marked *(planned)* is specified, not yet shipped. The first shippable target is `v0.1.0` — one chapter, one book, end to end, offline.

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

The core pipeline is **provider-agnostic**: every external dependency (LLM, TTS) sits behind a small interface, so the project works fully offline with [Ollama](https://ollama.com) + [Piper](https://github.com/rhasspy/piper), or optionally against cloud free tiers (Gemini, edge-tts) when you want higher accuracy — see [Extension model](#extension-model).

## Prerequisites

- **Python 3.10+**
- **Offline path (recommended, $0, no accounts):**
  - [Ollama](https://ollama.com) installed and running (`ollama serve`), with a model: `ollama pull qwen2.5:7b` *(planned: auto-pull in v0.1.0)*
  - [Piper TTS](https://github.com/rhasspy/piper/releases) binary on `PATH` plus a voice model (`en_US-amy-medium.onnx` + `.onnx.json`)
  - [ffmpeg](https://ffmpeg.org/download.html)
- **Cloud path (optional):** a Gemini API key for the LLM free tier, or nothing extra if you stay offline.

## Quick start

> 🎥 *(planned: a 3-minute demo video, recorded when v0.1.0 lands.)*

```bash
pip install audiobard[llm-ollama,tts-piper]
audiobard generate book.epub --output audiobook.mp3
```

Walkthrough of what happens on that one command — see [How it works](#how-it-works).

Until the first PyPI release, install from source:

```bash
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-ollama,tts-piper]"
```

## Command reference *(planned for v0.1.0)*

| Command | What it does |
|---|---|
| `audiobard generate <book> -o <out>` | Full pipeline: parse → attribute → synthesize → assemble |
| `audiobard benchmark` | Attribution accuracy against the hand-labeled gold standard (`eval/gold_standard/`) |
| `audiobard stats` | Cache hit rate, tokens, per-book state |
| `audiobard voices` | List available TTS voices for a locale |
| `audiobard validate-config` | Check config, providers, and model availability |
| `audiobard generate --dry-run` | Parse + LLM attribution only — no synthesis (fast prompt iteration) |

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
└── docs/                         # (planned) provider guides
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

Adding a provider = one class in one file + one config example + tests. See `docs/adding-a-provider.md` *(planned)*.

## Contributing

Thinking about a PR? Read [CONTRIBUTING.md](CONTRIBUTING.md) first — it states the one rule everything follows from, what gets merged, what gets declined, and why. All contributions are governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

**Quick orientation for new contributors:** the repo ships labeled issues — [`good first issue`](https://github.com/oscarbol09/audiobard/labels/good%20first%20issue) for onboarding, [`help wanted`](https://github.com/oscarbol09/audiobard/labels/help%20wanted) for meatier tasks, and [`ethics-review`](https://github.com/oscarbol09/audiobard/labels/ethics-review) for features that touch identity or consent.

## Ethics & responsible use

AudioBard converts public-domain text to audio. The following are explicitly out of scope, and require an `ethics-review` RFC before any implementation PR is accepted: voice cloning without consent, DRM circumvention, impersonation/deepfakes, and bulk generation for spam. Full policy in the [development plan, §10](AudioBard_DevPlan.md) and the [ethics-review issue](https://github.com/oscarbol09/audiobard/issues/7).

## License

MIT — see [LICENSE](LICENSE). The gold standard dataset (`eval/gold_standard/`) is CC0.