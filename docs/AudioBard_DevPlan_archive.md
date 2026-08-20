# AudioBard: Development Plan
## AI-Powered Audiobook Generator with Multi-Character Voice Synthesis

---

## ⚖️ License & Usage Notice

**License**: MIT
**Permitted use**: Personal, educational, research, non-commercial.
**Commercial use**: Not permitted with the default cloud LLM free tiers (see §3). For commercial deployments, self-host an open LLM (Ollama/vLLM, §3.4) or upgrade to paid API tiers at your own cost.

This notice is enforced via `LICENSE` and a runtime check in `audiobard/cli.py` that warns when commercial env vars are detected.

---

## 📖 Project Description

**AudioBard** is an open-source audiobook generator that:

1. Parses classic literary texts in the public domain (TXT, EPUB).
2. Automatically detects who speaks on each line (Narrator, Character_A, Character_B, …).
3. Assigns unique, expressive voices to each character, filtered by tone/gender/age.
4. Generates audiobooks with natural intonation using neural text-to-speech.
5. Maintains voice consistency across chapters via a persistent mapping.

**Primary test case**: *White Nights* by Fyodor Dostoevsky (Project Gutenberg #10054).
**Stress test**: *Pride and Prejudice* by Jane Austen (high dialog density, implicit attribution).

---

## 🎯 Objectives & Success Criteria

### MVP (v0.1.0 — Weeks 1–3)

- [ ] Functional parser for TXT/EPUB formats
- [ ] Dialog attribution via pluggable LLM client (≥90% accuracy on *Pride & Prejudice* Chapter 3 gold standard)
- [ ] Voice synthesis via pluggable TTS provider (Piper offline + Edge-TTS cloud)
- [ ] Persistent character ↔ voice mapping across chapters (SQLite)
- [ ] MP3 output with normalized volume
- [ ] Tone-aware voice assignment (LLM returns `tone` → voice pool filter)
- [ ] End-to-end pipeline runs 1 chapter (~1000 words) in <5 min
- [ ] Works offline (Piper + Ollama) with zero network calls

### Post-MVP (v0.2.0 — Weeks 4–6)

- [ ] Emotional intonation (rate/pitch/pause mapping per emotion)
- [ ] M4B output with chapter metadata + bookmarks
- [ ] CLI: `audiobard generate book.epub --output audiobook.m4b`
- [ ] Local request cache (hash → JSON in SQLite, ≥60% hit rate on reprocess)
- [ ] Async pipeline with semaphore-respecting rate limits

### Future (v0.3.0+)

- [ ] Web UI for book upload
- [ ] Multi-language support (locale-aware voice pools)
- [ ] Voice cloning with XTTS-v2 (with explicit ethics disclaimer, §10)
- [ ] PDF support (only if community demand justifies OCR work)

### Operational Success Metrics (measurable)

| Metric | MVP target | Post-MVP target | How measured |
|---|---|---|---|
| Dialog attribution accuracy | ≥90% | ≥95% | `eval/benchmark.py` against gold standard |
| Voice consistency | 100% same voice per character across chapters | 100% | `tests/test_consistency.py` |
| Pipeline time / 1000 words | <5 min | <1 min | `time` CLI wrapper |
| Cache hit rate (reprocess) | n/a | ≥60% | `audiobard stats` |
| Test coverage | ≥70% | ≥85% | `pytest --cov` |

The **gold standard** is a hand-labeled JSON of *Pride & Prejudice* Chapter 3 (~300 interventions) shipped in `eval/gold_standard/p_and_p_ch3.json`. Contributors must not modify it; PRs that improve the LLM prompt are validated against it.

---

## 🛠️ Tech Stack (100% Free, FOSS-First)

| Component | Primary (Recommended) | Fallback | Why |
|---|---|---|---|
| **LLM (Attribution)** | **Ollama** local (Llama-3.1-8B-Instruct, Qwen2.5-7B) | Gemini 1.5 Flash (cloud, free tier) | Offline-capable, no TOS risk, privacy |
| **TTS (Synthesis)** | **Piper TTS** (offline, ONNX, MIT) | edge-tts (cloud, no SLA) | No single point of failure, reproducible |
| **Parsing** | BeautifulSoup4 + ebooklib (EPUB) | Standard library (TXT) | Mature, well-maintained |
| **Audio** | pydub + ffmpeg | — | Industry standard |
| **Schemas & Validation** | Pydantic v2 | — | Type-safe JSON contracts |
| **Local DB** | SQLite (stdlib) | — | No external deps |
| **Async** | asyncio + httpx | — | Native, no extra runtime |
| **Packaging** | pyproject.toml (PEP 621) | — | Modern standard |
| **Testing** | pytest + pytest-asyncio + pytest-cov | — | Standard |
| **Linting** | ruff + mypy | — | Fast, modern |
| **CI** | GitHub Actions | — | Free for OSS |
| **Version Control** | Git | — | — |

### Removed from previous version

- ❌ **PDF (pdfplumber)**: premature; OCR quality on classics is poor. Re-add when requested.
- ❌ **PickleDB**: unmaintained since 2022; SQLite is stdlib.
- ❌ **NVIDIA NIM as primary**: proprietary API with unclear TOS; keep as optional plug-in only.

### LLM Provider Comparison (Free Tier)

| Provider | Model | RPM | Tokens/Month | JSON | Offline | TOS risk | Cost |
|---|---|---|---|---|---|---|---|
| **Ollama (local)** | Llama-3.1-8B-Instruct-Q4_K_M | Unlimited | Unlimited | ✅ (via Pydantic schema in prompt) | ✅ | None | **$0** (hardware: 8 GB RAM) |
| **Ollama (local)** | Qwen2.5-7B-Instruct-Q4_K_M | Unlimited | Unlimited | ✅ | ✅ | None | **$0** |
| **Gemini API** | gemini-2.0-flash (verify at ai.google.dev) | 60 | 1M | ✅ Native | ❌ | ⚠️ Non-commercial only | **$0** (free tier) |
| **OpenRouter** | deepseek-chat-v3 (free) | 20 | ~90K | ✅ | ❌ | ⚠️ Non-commercial | **$0** (free tier) |

**Recommendation for MVP**: Ollama with Qwen2.5-7B for the primary path (offline, no TOS, reproducible). Gemini as opt-in for users who want better accuracy and accept the TOS constraint.

---

## 📋 Development Phases

### PHASE 1: Infrastructure & Setup (Week 1, 8–12 h)

#### 1.1 Repository Scaffold
**Tasks**:
- [ ] Initialize repo with `pyproject.toml`, `README.md`, `LICENSE` (MIT), `CODE_OF_CONDUCT.md` (Contributor Covenant), `CONTRIBUTING.md`, `.gitignore`, `.editorconfig`
- [ ] Create GitHub repo with issue templates (`bug.yml`, `feature.yml`) and PR template
- [ ] Enable branch protection on `main` (require CI + 1 review)
- [ ] Configure GitHub Actions CI:
  - `lint`: ruff + mypy
  - `test`: pytest on Python 3.10, 3.11, 3.12 (matrix)
  - `coverage`: ≥70% gate for MVP

**Directory structure**:
```
audiobard/
├── src/audiobard/
│   ├── __init__.py
│   ├── cli.py                    # argparse / typer entry point
│   ├── config.py                 # Pydantic Settings model
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract BookParser
│   │   ├── text_parser.py
│   │   └── epub_parser.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract LLMClient + Pydantic schemas
│   │   ├── ollama_client.py      # PRIMARY (offline)
│   │   ├── gemini_client.py      # OPT-IN (cloud)
│   │   ├── openrouter_client.py  # OPT-IN (cloud)
│   │   └── prompts.py            # Versioned prompt templates with few-shot
│   ├── tts/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract TTSProvider
│   │   ├── piper_provider.py     # PRIMARY (offline)
│   │   ├── edge_provider.py      # OPT-IN (cloud)
│   │   └── voice_mapper.py       # Tone-aware voice pool + hash fallback
│   ├── audio/
│   │   ├── __init__.py
│   │   └── processor.py          # async wrapper around pydub
│   ├── pipeline.py               # AudioBookPipeline orchestrator
│   └── persistence.py            # SQLite: speakers, voices, cache, runs
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_llm_*.py
│   ├── test_tts_*.py
│   ├── test_audio.py
│   └── test_pipeline.py
├── eval/
│   ├── gold_standard/
│   │   └── p_and_p_ch3.json      # hand-labeled, immutable
│   └── benchmark.py              # attribution accuracy scorer
├── data/
│   ├── books/                    # .gitignored, sample book for dev
│   ├── personas.example.json
│   └── voice_mapping.example.json
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── release.yml
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── pyproject.toml
├── README.md
├── LICENSE
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .gitignore
```

**Dependencies** (`pyproject.toml`):
```toml
[project]
name = "audiobard"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "httpx>=0.27",
  "beautifulsoup4>=4.12",
  "ebooklib>=0.18",
  "pydub>=0.25",
  "typer>=0.12",
  "rich>=13.7",
]

[project.optional-dependencies]
llm-ollama = ["ollama>=0.2"]
llm-gemini = ["google-generativeai>=0.4"]
llm-openrouter = []  # uses httpx only
tts-piper = []       # uses subprocess, no Python deps
tts-edge = ["edge-tts>=6.1"]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "pytest-cov>=4.1", "ruff>=0.4", "mypy>=1.9", "respx>=0.21"]
```

**Estimated time**: 3–4 h (incl. CI setup)

---

#### 1.2 Text & EPUB Parser
**Tasks**:
- [ ] `parser/base.py`: `BookParser` ABC with `parse() -> list[Paragraph]`
- [ ] `parser/text_parser.py`: handles UTF-8, Project Gutenberg headers/footers (regex strip), normalizes whitespace, detects chapter boundaries
- [ ] `parser/epub_parser.py`: extracts chapters via spine metadata, preserves order, strips frontmatter/backmatter
- [ ] `Paragraph` Pydantic model: `text`, `chapter`, `index`, `is_dialog` (heuristic: contains quotes or dialogue dash)
- [ ] Statistics: `ParserStats` (total paragraphs, words, dialog ratio, per-chapter word count)
- [ ] Tests: 3 sample books (one TXT, two EPUBs of varying structure)

**Dependencies**: 1.1
**Estimated time**: 4–6 h

---

#### 1.3 LLM Client & Prompts (Pydantic-Schema + Few-Shot)
**Tasks**:
- [ ] `llm/base.py`:
  - `LLMClient` ABC with `extract_characters(text) -> CharactersResult` and `attribute_dialog(chapter, characters) -> AttributionResult`
  - Async interface: `async def extract_characters(...)`
  - Built-in retry with exponential backoff + jitter
  - Token/latency logging via `structlog`
  - Schema validation via Pydantic on every response (drop-and-retry on schema mismatch, max 2 retries)

- [ ] **Pydantic schemas** (single source of truth, reused across providers):
  ```python
  class Character(BaseModel):
      canonical_id: str = Field(pattern=r"^(Narrator|Character_[A-Z])$")
      name: str
      aliases: list[str]
      tone: Literal["warm", "cold", "agitated", "calm", "mysterious", "cheerful", "melancholic", "authoritative", "timid", "sarcastic"]
      gender_hint: Literal["male", "female", "neutral"]
      age_hint: Literal["child", "young", "adult", "elderly"]

  class CharactersResult(BaseModel):
      characters: list[Character]

  class DialogLine(BaseModel):
      text: str
      speaker: str  # must match a canonical_id from CharactersResult
      emotion: Literal["neutral", "happy", "sad", "angry", "fearful", "surprised", "whisper", "sarcastic"] = "neutral"

  class AttributionResult(BaseModel):
      lines: list[DialogLine]
  ```

- [ ] `llm/prompts.py`: versioned prompt templates with **3-layer structure**:
  1. **System (role + constraints)**: "You are a literary attribution expert. You output ONLY valid JSON matching this schema: {schema}. Never use markdown. Never invent characters not in the list."
  2. **Schema injection**: Pydantic JSON schema dumped into prompt
  3. **Few-shot examples**: 3 worked examples (clear dialog, ambiguous attribution, narration-only)

  Two templates:
  - `EXTRACT_CHARACTERS_V1` → `CharactersResult`
  - `ATTRIBUTE_DIALOG_V1` → `AttributionResult`

- [ ] `llm/ollama_client.py`: uses `ollama` Python SDK, `format=schema` for native JSON mode (Llama 3.1+ and Qwen 2.5+ support it)
- [ ] `llm/gemini_client.py`: uses `response_mime_type="application/json"` + `response_schema=CharactersResult.model_json_schema()`
- [ ] `llm/openrouter_client.py`: uses `response_format={"type": "json_object"}` + manual Pydantic validation

**Dependencies**: 1.1
**Estimated time**: 8–10 h (Pydantic schemas + few-shot prompts take longer than the previous version's sketches)

---

#### 1.4 Voice Mapping (Tone-Aware)
**Tasks**:
- [ ] `tts/voice_mapper.py`:
  - Loads voice pool per locale (e.g., `voices/en_US.json`) with metadata: `{id, gender, age, energy, sample_text}`
  - **`assign(character: Character) -> Voice`** algorithm:
    1. Filter pool by `gender_hint` (mandatory) and `age_hint` (best-effort)
    2. From filtered pool, score by cosine similarity between `tone` and voice metadata
    3. Deterministic tie-break: `hash(canonical_id) % len(filtered_pool)`
    4. If filtered pool is empty, fall back to hash-based assignment across full pool and log a warning
  - Save/load `voice_mapping.json` (versioned schema)
  - Reproducible: same `characters.json` → same mapping (for tests)

- [ ] `personas.example.json`:
  ```json
  {
    "version": 1,
    "locale": "en_US",
    "assignments": {
      "Narrator":      {"voice_id": "en_US-amy-medium",     "rate": 1.0, "pitch": 1.0},
      "Character_A":   {"voice_id": "en_US-joe-medium",      "rate": 1.0, "pitch": 1.05},
      "Character_B":   {"voice_id": "en_US-kusal-medium",    "rate": 0.95,"pitch": 0.95}
    }
  }
  ```

**Dependencies**: 1.1
**Estimated time**: 4–5 h

---

### PHASE 2: Pipeline Core (Week 2, 14–18 h)

#### 2.1 TTS Provider (Async)
**Tasks**:
- [ ] `tts/base.py`: `TTSProvider` ABC
  - `async def synthesize(text: str, voice: Voice, emotion: Emotion) -> bytes` (MP3)
  - `async def list_voices(locale: str) -> list[Voice]`
  - Built-in LRU cache (in-memory, max 500 MB) keyed by `(text_hash, voice_id, emotion)`
  - Disk cache: `~/.cache/audiobard/tts/{hash}.mp3` (configurable)

- [ ] `tts/piper_provider.py` (PRIMARY):
  - Subprocess wrapper around `piper` binary
  - Batch synthesis: queue → `asyncio.gather` with concurrency limit
  - Downloads voice model on first use (cached in `~/.cache/audiobard/piper/`)

- [ ] `tts/edge_provider.py` (OPT-IN):
  - Wraps `edge-tts` library
  - SSML support for emotion → prosody mapping
  - Documents: "Microsoft may change/limit this endpoint without notice"

- [ ] Emotion → prosody mapping (shared by both providers):
  ```python
  EMOTION_PROSODY = {
    "happy":      {"rate": 1.10, "pitch": 1.08, "pause_after_ms": 200},
    "sad":        {"rate": 0.85, "pitch": 0.92, "pause_after_ms": 400},
    "angry":      {"rate": 1.15, "pitch": 1.05, "pause_after_ms": 250},
    "fearful":    {"rate": 1.05, "pitch": 1.12, "pause_after_ms": 300},
    "surprised":  {"rate": 1.08, "pitch": 1.15, "pause_after_ms": 250},
    "whisper":    {"rate": 0.80, "pitch": 0.95, "pause_after_ms": 350},
    "sarcastic":  {"rate": 1.02, "pitch": 1.03, "pause_after_ms": 300},
    "neutral":    {"rate": 1.00, "pitch": 1.00, "pause_after_ms": 250},
  }
  ```

**Dependencies**: 1.4
**Estimated time**: 6–8 h

---

#### 2.2 Audio Processor (Async)
**Tasks**:
- [ ] `audio/processor.py`:
  - `AudioProcessor` with async API, sync work runs in `ThreadPoolExecutor` (pydub/ffmpeg is blocking)
  - `concatenate(clips: list[AudioClip]) -> bytes`: applies silence gaps, normalizes volume (`-16 LUFS` via `pydub` effects)
  - `export_mp3(audio, path)` and `export_m4b(audio, path, chapters: list[Chapter])`
  - M4B chapter metadata via `mutagen` MP4 chapters atom

- [ ] `AudioClip` Pydantic model: `mp3_bytes`, `speaker`, `emotion`, `duration_ms`
- [ ] Tests: concatenate 10 dummy clips, verify silence gaps, verify M4B chapter markers (use `ffprobe`)

**Dependencies**: 2.1
**Estimated time**: 5–7 h

---

#### 2.3 Pipeline Orchestrator
**Tasks**:
- [ ] `pipeline.py`:
  - `AudioBookPipeline` orchestrator
  - Flow: `parse → extract_characters (LLM) → assign_voices → attribute_dialog (LLM, chunked) → synthesize (async, rate-limited) → assemble`
  - **Chunking**: 1500 words per LLM attribution call (sweet spot for context vs reliability)
  - **Rate limiting**: `asyncio.Semaphore` per LLM/TTS provider (defaults from config)
  - **Progress**: `rich.progress.Progress` bar with ETA
  - **Resumability**: pipeline state stored in SQLite (`pipeline_runs` table); `--resume` flag restarts from last checkpoint
  - **Logging**: structured JSON logs via `structlog` (latency, tokens, cache hits, errors)

- [ ] CLI: `audiobard generate book.epub -o audiobook.mp3 --llm ollama --tts piper`
- [ ] End-to-end smoke test: 1 chapter of *White Nights*, <5 min

**Dependencies**: 1.2, 1.3, 2.1, 2.2
**Estimated time**: 6–8 h

---

### PHASE 3: Quality & Persistence (Week 3, 12–15 h)

#### 3.1 Local Request Cache
**Tasks**:
- [ ] SQLite table `llm_cache`:
  ```sql
  CREATE TABLE llm_cache (
    prompt_hash TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hits INTEGER DEFAULT 0
  );
  ```
- [ ] Cache key: SHA-256 of `(prompt_version, model, temperature, input_text)`
- [ ] On LLM error: do NOT cache; on success: store
- [ ] CLI: `audiobard stats` shows cache hit rate

**Dependencies**: 2.3
**Estimated time**: 3–4 h

---

#### 3.2 Persistent Speaker ↔ Voice Mapping
**Tasks**:
- [ ] SQLite tables:
  ```sql
  CREATE TABLE books (
    id TEXT PRIMARY KEY,
    title TEXT,
    author TEXT,
    source_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    book_id TEXT REFERENCES books(id),
    canonical_id TEXT,
    name TEXT,
    tone TEXT,
    gender_hint TEXT,
    age_hint TEXT,
    UNIQUE(book_id, canonical_id)
  );

  CREATE TABLE speaker_voice_map (
    book_id TEXT REFERENCES books(id),
    canonical_id TEXT,
    voice_id TEXT,
    rate REAL,
    pitch REAL,
    PRIMARY KEY (book_id, canonical_id)
  );
  ```
- [ ] `persistence.PersistenceManager`: typed CRUD methods returning Pydantic models
- [ ] Pipeline: on new chapter, load existing mapping first; new characters are appended, never reassigned

**Dependencies**: 3.1
**Estimated time**: 4–5 h

---

#### 3.3 Attribution Benchmark
**Tasks**:
- [ ] `eval/gold_standard/p_and_p_ch3.json`: hand-labeled dialog + speaker (immutable)
- [ ] `eval/benchmark.py`:
  ```bash
  audiobard benchmark --llm ollama --model qwen2.5:7b
  # Output:
  #   Accuracy: 92.3% (276/299 lines)
  #   Per-character: Narrator 100%, Elizabeth 94%, Darcy 89%, ...
  #   Confusion matrix: ...
  ```
- [ ] CI workflow `benchmark.yml` (weekly cron + manual trigger): tracks accuracy regression
- [ ] Documentation in `CONTRIBUTING.md`: "Improving prompts? Run the benchmark, your PR must not decrease accuracy."

**Dependencies**: 2.3
**Estimated time**: 5–6 h (incl. labeling the gold standard)

---

### PHASE 4: Documentation & Release (Week 3–4, 8–10 h)

#### 4.1 README & Docs
**Tasks**:
- [ ] `README.md`: quick start (5 min to first audiobook), architecture diagram, supported formats, ethics disclaimer, contributing link
- [ ] `docs/prompt-engineering.md`: how prompts are versioned, how to test a new model
- [ ] `docs/adding-a-provider.md`: how to add a new `LLMClient` or `TTSProvider`
- [ ] `CHANGELOG.md` (Keep a Changelog format)

**Dependencies**: 3.3
**Estimated time**: 4–5 h

---

#### 4.2 Configuration & CLI Polish
**Tasks**:
- [ ] `config.py`: `AudioBardConfig` Pydantic Settings, loads from `~/.config/audiobard/config.yaml` + env vars
- [ ] CLI: `typer`-based with subcommands (`generate`, `benchmark`, `stats`, `voices`, `validate-config`)
- [ ] `--dry-run`: parse + LLM attribution only, no synthesis (saves time when iterating on prompts)

**Dependencies**: 4.1
**Estimated time**: 3–4 h

---

#### 4.3 v0.1.0 Release
**Tasks**:
- [ ] Tag `v0.1.0-MVP`, GitHub release with audio sample (5 min from *White Nights*)
- [ ] Post in: r/selfhosted, r/Python, Hacker News (Show HN), opensource.audio Discord
- [ ] Submit to: awesome-open-source-audio list

**Dependencies**: 4.1, 4.2
**Estimated time**: 1 h

---

## 📊 Timeline (revised estimates, contributor-friendly)

Estimates assume a contributor familiar with Python but new to LLM APIs and TTS. If you're experienced with both, halve them.

```
WEEK 1  (Infrastructure)
├─ Day 1-2:   Phase 1.1 (Repo + CI + pyproject)         [6-8 h]
├─ Day 3-4:   Phase 1.2 (Parser)                        [4-6 h]
└─ Day 5:     Phase 1.3 part A (Pydantic schemas)       [3-4 h]
   TOTAL: 13-18 h

WEEK 2  (Core)
├─ Day 1-2:   Phase 1.3 part B (Prompts + clients)      [5-6 h]
├─ Day 3:     Phase 1.4 (Voice mapper)                  [4-5 h]
├─ Day 4-5:   Phase 2.1 (TTS providers)                 [6-8 h]
└─ Day 5:     Phase 2.2 (Audio processor)               [5-7 h]
   TOTAL: 20-26 h

WEEK 3  (Quality)
├─ Day 1:     Phase 2.3 (Pipeline orchestrator)         [6-8 h]
├─ Day 2:     Phase 3.1 (Cache)                         [3-4 h]
├─ Day 3:     Phase 3.2 (Persistence)                   [4-5 h]
└─ Day 4-5:   Phase 3.3 (Benchmark + gold standard)     [5-6 h]
   TOTAL: 18-23 h

WEEK 4  (Release)
├─ Day 1-2:   Phase 4.1 (Docs)                          [4-5 h]
├─ Day 3:     Phase 4.2 (CLI polish)                    [3-4 h]
└─ Day 4:     Phase 4.3 (Release + announce)            [1 h]
   TOTAL: 8-10 h

GRAND TOTAL: 59-77 h  (MVP complete, contributor-pace)
              ~35-45 h (experienced developer)
```

---

## 🎨 Technical Considerations

### 1. Pluggable architecture (anti-fragile)

Every external dependency goes behind an interface (`LLMClient`, `TTSProvider`, `BookParser`). Concrete implementations can be swapped via config without code changes:

```yaml
# config.yaml
llm:
  provider: ollama      # ollama | gemini | openrouter
  model: qwen2.5:7b
tts:
  provider: piper       # piper | edge
  locale: en_US
```

This means: if Piper goes unmaintained, contributors can add `coqui_provider.py` in isolation. If Ollama changes its API, only `ollama_client.py` is touched.

### 2. API Rate Limiting & Resilience

**Local-first advantage**: Ollama and Piper have no rate limits. The whole pipeline can run offline, in CI, on a laptop. Cloud providers are an opt-in speedup.

**For cloud fallback (Gemini/OpenRouter)**:
- `asyncio.Semaphore` per provider (defaults: 30 for Gemini, 15 for OpenRouter)
- Exponential backoff: `min(60, 2^attempt + jitter)`
- Auto-fallback to next provider on persistent failure (config-driven chain)

### 3. TOS Awareness

| Provider | Free tier TOS | Safe for commercial? |
|---|---|---|
| Ollama | MIT (self-hosted) | ✅ Yes |
| Piper | MIT | ✅ Yes |
| Gemini free | Non-commercial only | ❌ No |
| OpenRouter free | Non-commercial only | ❌ No |

`audiobard/cli.py` checks for `COMMERCIAL_USE=true` env var and refuses to instantiate cloud providers when set. This is a soft guardrail, not legal advice.

### 4. Ambiguous Dialog Resolution

Cases like:
> "It was a cold night. I looked out the window.
> — What do you see there? — someone asked.
> I said nothing."

Strategy (in `ATTRIBUTE_DIALOG_V1`):
1. Provide 5-paragraph sliding window (before + current + after)
2. Explicit instruction: "When the speaker is ambiguous, prefer the most recently named character who is present in the scene. If truly indeterminate, output `speaker: 'Narrator'` and add a flag in your reasoning."
3. Benchmark against gold standard to measure, don't guess.

### 5. Voice Consistency Across Chapters

Three layers of defense:
1. **Canonical IDs** (no aliases in prompts — `Character_A`, not "she")
2. **SQLite mapping** (`speaker_voice_map` keyed on `book_id + canonical_id`)
3. **Deterministic voice assignment** (hash tie-break → reproducible across machines)

### 6. Async Concurrency Model

```
LLM calls (async, semaphore-limited) ──┐
                                       ├─► asyncio.gather ─► AudioClip queue
TTS calls (async, semaphore-limited) ──┘                        │
                                                               ▼
                                              ThreadPoolExecutor (pydub/ffmpeg)
                                                               │
                                                               ▼
                                                          Final MP3/M4B
```

LLM and TTS are I/O-bound → `asyncio`. `pydub`/`ffmpeg` are CPU-bound and blocking → offloaded to `ThreadPoolExecutor` (default: `min(8, cpu_count())` workers).

---

## 🧪 Testing Strategy

- **Unit tests**: per-module, mock external calls (`respx` for httpx, `pytest-mock` for subprocess)
- **Integration tests**: 1 short chapter end-to-end with mocked LLM/TTS (deterministic fixtures)
- **Benchmark**: weekly CI run against gold standard (catches prompt regressions)
- **Smoke test**: real *White Nights* Chapter 1 runs in <5 min on CI (uses Ollama + Piper, no API keys needed)
- **Coverage gate**: ≥70% for MVP, ≥85% for v0.2.0

---

## � Resources & References

- **Test corpus**:
  - *White Nights*: https://www.gutenberg.org/ebooks/10054
  - *Pride and Prejudice*: https://www.gutenberg.org/ebooks/1342 (gold standard chapter)
  - *Sherlock Holmes* (A Study in Scarlet): https://www.gutenberg.org/ebooks/244
- **Piper TTS voices**: https://github.com/rhasspy/piper/releases (download `.onnx` + `.onnx.json`)
- **Ollama models**: https://ollama.com/library (qwen2.5, llama3.1)
- **Pydantic v2**: https://docs.pydantic.dev/latest/
- **ffmpeg**: https://ffmpeg.org/download.html
- **mutagen** (M4B chapters): https://mutagen.readthedocs.io/
- **Contributor Covenant**: https://www.contributor-covenant.org/

---

## 🔒 Ethics & Responsible Use (v0.1.0 from day 1)

AudioBard is a tool for converting public-domain text to audio. The following are **explicitly out of scope** and will not be supported without a community RFC:

1. **Voice cloning without consent**: XTTS-v2 integration (post-MVP) requires a documented consent flow. Default behavior: disabled.
2. **Bypassing paywalled content**: no DRM circumvention tools.
3. **Impersonation / deepfakes**: no helpers for creating audio that misrepresents a real person.
4. **Bulk generation for spam/astroturfing**: rate limits and per-run cost logging are baked in.

Contributors proposing features in these areas must open an issue with the `ethics-review` label before submitting a PR.

---

## 📝 Notes

- **Total cost**: $0 (all paths use free + FOSS)
- **Hardware (offline path)**: 8 GB RAM minimum (Qwen 2.5 7B Q4); CPU i5 is sufficient, GPU optional
- **Hardware (cloud path)**: any machine with Python 3.10+
- **Effort**: 59–77 h at contributor pace, 35–45 h for experienced devs
- **License**: MIT (code) + CC0 for gold standard (`eval/gold_standard/`)
- **First release target**: 4 weeks from project start

---

**v2.0 of Development Plan | Last verified: 2026-08-19**
