# Contributing to AudioBard

Thanks for your interest in contributing! 🎉

This document covers everything you need to know to submit issues, propose features, and open pull requests.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Project structure](#project-structure)
- [Development setup](#development-setup)
- [Reporting bugs](#reporting-bugs)
- [Suggesting features](#suggesting-features)
- [Pull requests](#pull-requests)
- [Style guide](#style-guide)
- [Testing](#testing)
- [Prompt engineering guidelines](#prompt-engineering-guidelines)
- [Adding a new LLM or TTS provider](#adding-a-new-llm-or-tts-provider)

## Code of conduct

This project follows the [Contributor Covenant Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## Project structure

```
audiobard/
├── src/audiobard/       # Library code
│   ├── parser/          # TXT/EPUB parsers
│   ├── llm/             # LLM clients + prompts
│   ├── tts/             # TTS providers + voice mapper
│   ├── audio/           # Audio assembly
│   ├── pipeline.py      # Orchestrator
│   └── cli.py           # CLI entry point
├── tests/               # pytest suite
├── eval/                # Benchmark + gold standard
└── data/                # Sample books (gitignored)
```

External dependencies (LLMs, TTS engines) are isolated behind interfaces (`LLMClient`, `TTSProvider`). To change behavior, you usually only need to touch one provider implementation and the corresponding tests.

## Development setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- A model pulled: `ollama pull qwen2.5:7b` (or `llama3.1:8b`)
- [Piper TTS](https://github.com/rhasspy/piper/releases) binary on PATH
- [ffmpeg](https://ffmpeg.org/download.html) installed
- A voice model from [Piper releases](https://github.com/rhasspy/piper/releases) (e.g. `en_US-amy-medium.onnx` + `.onnx.json`)

### Steps

```bash
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-ollama,tts-piper]"
pre-commit install          # if .pre-commit-config.yaml is present
pytest                      # run the test suite
```

### Running the benchmark

```bash
audiobard benchmark --llm ollama --model qwen2.5:7b
```

This evaluates attribution accuracy against the gold standard (`eval/gold_standard/p_and_p_ch3.json`). **Any PR that modifies `src/audiobard/llm/prompts.py` must include benchmark output showing no regression.**

## Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug.yml). Include:

- Python version (`python --version`)
- AudioBard version (`audiobard --version`)
- OS and architecture
- Minimal reproduction snippet
- Full error traceback (if applicable)

## Suggesting features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature.yml). Before opening a PR for a new feature:

1. Open an issue describing the use case
2. Wait for maintainer feedback
3. Reference the issue from your PR

Features touching voice cloning, identity, or impersonation require the `ethics-review` label and an explicit RFC. See the development plan §10.

## Pull requests

1. Fork the repo and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes. Follow the [style guide](#style-guide).
3. Add or update tests. PRs that decrease coverage below 70% will be rejected.
4. Run the full CI suite locally:
   ```bash
   ruff check .
   ruff format .
   mypy src/audiobard
   pytest --cov=audiobard --cov-report=term-missing
   ```
5. If you modified `prompts.py`, run the benchmark and attach output.
6. Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
7. Push and open a PR. Reference any related issues.
8. Wait for review. At least 1 approving review is required before merge.

PR titles follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` code change with no behavior change
- `test:` test additions/corrections
- `chore:` tooling, CI, dependencies

Example: `feat: add Piper TTS provider with emotion prosody mapping`

## Style guide

- **Python**: follow PEP 8 + ruff defaults. Max line length 100.
- **Type hints**: required for all public APIs. Use `from __future__ import annotations` if needed.
- **Pydantic**: use Pydantic models for all data structures that cross module boundaries.
- **Async**: prefer `async def` for I/O-bound code (LLM, TTS, filesystem). CPU-bound work goes through `asyncio.to_thread` or `ThreadPoolExecutor`.
- **Logging**: use `structlog` (already a dependency). Never `print()` for diagnostics.
- **Error messages**: actionable. Include what failed and how to fix it.
- **Docstrings**: Google style for modules, classes, and public functions.

## Testing

- **Unit tests** (`tests/`): mock external calls. Use `respx` for httpx, `pytest-mock` for subprocess.
- **Integration tests** (`tests/integration/`): end-to-end with deterministic fixtures. Mark with `@pytest.mark.integration`.
- **Benchmark** (`eval/benchmark.py`): runs against gold standard. CI runs weekly + on prompt changes.

Coverage gate: 70% for MVP, 85% for v0.2.0.

## Prompt engineering guidelines

Prompts live in `src/audiobard/llm/prompts.py` and are versioned (`PROMPT_V1`, `PROMPT_V2`, ...). When modifying prompts:

1. **Never edit a versioned prompt in place.** Add a new version (`PROMPT_V2`) and switch the default in `llm/__init__.py`.
2. **Run the benchmark before and after.** The new version must not regress accuracy.
3. **Include few-shot examples** (3-5 worked examples covering edge cases).
4. **Pydantic-validate responses.** The schema is the source of truth.
5. **Document the change** in the prompt docstring: what changed, why, expected effect.

## Adding a new LLM or TTS provider

1. Subclass the relevant ABC (`LLMClient` or `TTSProvider`).
2. Implement all abstract methods. Match the async/sync signature of the base.
3. Register the provider in the factory (`src/audiobard/llm/__init__.py` or `tts/__init__.py`).
4. Add a config example to `config.example.yaml`.
5. Add tests with mocked network calls.
6. Update `README.md` "Supported providers" table.

See `docs/adding-a-provider.md` (TODO: write this in Phase 4.1) for a detailed walkthrough.

## Questions?

Open a [discussion](https://github.com/oscarbol09/audiobard/discussions) or reach out via issues.
