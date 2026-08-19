# Contributing to AudioBard

Thanks for your interest. AudioBard is a small project with a strong
opinion: **one change per PR, backed by real evidence**. This document is
short on purpose — the longer it gets, the less it gets read.

- [Code of conduct](#code-of-conduct)
- [What gets merged (and what doesn't)](#what-gets-merged-and-what-doesnt)
- [Development setup](#development-setup)
- [Reporting bugs](#reporting-bugs)
- [Opening a pull request](#opening-a-pull-request)
- [The benchmark bar](#the-benchmark-bar)
- [Style guide](#style-guide)
- [Testing](#testing)
- [Prompts: the versioning rule](#prompts-the-versioning-rule)
- [Adding a provider](#adding-a-provider)
- [The guards: touching tools/guards.py](#the-guards-touching-toolsguardspy)

## Code of conduct

[Contributor Covenant](./CODE_OF_CONDUCT.md). By participating you agree to
uphold it.

## What gets merged (and what doesn't)

The maintainer applies the same bar to every PR. Precedents shape the bar;
these are the recurring rejection reasons:

1. **Evidence of the real input, not a constructed one.** A fix for an
   input shape the actual code path never produces gets closed. Before
   opening a PR for a parser/LLM fix, show a real sample (a real EPUB/TXT
   file, a real provider response) that exhibits the condition. If you
   can't reproduce it in the real environment, say so — a "paused, not a
   verdict" PR is welcome, and it gets re-opened with evidence.
2. **Reproducible on current dependencies, through the real code path.** A
   test that injects a string by bypassing the actual reading path doesn't
   count as evidence. Show the actual command/output that fails.
3. **One change per PR.** Personal fork configuration (AGENTS.md, local
   scripts, editor config) never enters a PR. Separate concerns into
   separate PRs; mixed PRs are closed on sight.
4. **Duplicates lose to first-filed-with-tests.** Search open issues and
   PRs before implementing. If the same bug already has an issue or a PR
   with tests, the earlier one wins — no competing implementations.
5. **Tests must be real pins.** A test that copies the constant it watches
   drifts together with the file it should police. Derive the watched
   value from the source file when you can, and assert exact equality over
   every affected file, not substring membership.
6. **If a PR takes pieces of someone else's closed PR/issue**, the commits
   that use them must carry `Co-authored-by: Name <id+user@users.noreply.github.com>`
   for that author. No exception.

## Development setup

Prerequisites: Python 3.10+, [Ollama](https://ollama.com) running with a
pulled model (e.g. `ollama pull qwen2.5:7b`), the
[Piper](https://github.com/rhasspy/piper/releases) binary on PATH, and
[ffmpeg](https://ffmpeg.org/download.html).

```bash
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-ollama,tts-piper]"
pytest
```

Run the whole local gate the same way CI does:

```bash
ruff check src tests tools
mypy src/audiobard
pytest --cov=audiobard --cov-fail-under=70 -m "not integration"
python tools/guards.py
```

## Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug.yml) and include:

- Python version, `audiobard --version`, OS
- A minimal reproduction **that goes through the real code path** — the
  actual file or the actual provider response, not a paraphrase
- The full error traceback

Anything security-related goes to the [security policy](./SECURITY.md),
never into a public issue.

## Opening a pull request

1. Check for existing issues/PRs about the same bug first (see above).
2. Branch from `main` with a descriptive name: `fix/`, `feat/`, `docs/`.
3. Make the change. **One change per PR.** Keep the diff reviewable.
4. Add or update tests that would fail against the pre-fix code.
5. Run the local gate (above) until clean.
6. If you touched prompts or parsers, run the benchmark (next section) and
   attach its output to the PR.
7. Open the PR with the [template](.github/PULL_REQUEST_TEMPLATE.md),
   referencing any related issues. At least one approving review is
   required; the merge is squash or linear only.

Titles follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Messages in
English.

## The benchmark bar

`audiobard benchmark --llm ollama --model qwen2.5:7b` scores attribution
accuracy against the gold standard (`eval/gold_standard/p_and_p_ch3.json`).

**Any PR that changes `src/audiobard/llm/prompts.py`, the parsers, or the
attribution logic must include benchmark output showing no regression.**
Without it the PR is marked incomplete, not merged. This is the project's
core contract: quality is measured, not asserted.

## Style guide

- PEP 8 + ruff defaults, line length 100. Type hints on all public APIs.
- Pydantic models for every data structure crossing a module boundary —
  the LLM JSON schemas are generated from them.
- `async def` for I/O (LLM, TTS, filesystem); CPU-bound work via
  `asyncio.to_thread`.
- Logging via `structlog`; never `print()` for diagnostics.
- Docstrings: Google style for modules, classes, public functions.

## Testing

- Unit tests in `tests/` mock external calls (`respx` for httpx).
- Integration tests are marked `@pytest.mark.integration` and excluded
  from CI (they need local Ollama/Piper).
- Coverage gate: 70%.

## Prompts: the versioning rule

Prompts live in `src/audiobard/llm/prompts.py`, versioned
(`PROMPT_V1`, ...). **Never edit a versioned prompt in place** — add a new
version and switch the default, so the benchmark can compare versions.
Document what changed and why in the prompt's docstring.

## Adding a provider

1. Subclass the relevant ABC (`LLMClient` or `TTSProvider`).
2. Implement all abstract methods with the base's async/sync signature.
3. Register it in the factory (`src/audiobard/llm/__init__.py` or
   `tts/__init__.py`).
4. Add a config example and tests with mocked network calls.
5. Update the README providers table.
6. Providers that clone voices or impersonate real people trigger the
   `ethics-review` RFC requirement (dev plan §10) — open the RFC issue
   before implementing.

## The guards: touching tools/guards.py

`tools/guards.py` (run in CI) pins personal-data protection: `.env` never
committed, `data/books/` only allowlisted public-domain samples, no audio
output tracked, no literal API keys in source. Its allowlists
(`REQUIRED_IGNORE_RULES`, `ALLOWED_IGNORE_NEGATIONS`,
`ALLOWED_DATA_BOOK_FILES`, `SECRET_EXEMPT_PATHS`) are the reviewed
contract: if your change legitimately needs a new allowlist entry, add it
**in the same PR** with a comment explaining why. Changing a guard and
changing the thing it guards in separate PRs is a rejection.

## Questions?

Open an issue or ask in the PR itself. If an issue is long, make the ask
at the top.