# AGENTS.md — for AI coding agents working in this repo

AudioBard converts public-domain books into multi-voice audiobooks with a
local LLM and TTS, then optionally generates a "radio play" scene version
and narration track. See [AudioBard_DevPlan.md](AudioBard_DevPlan.md) for
the architecture and phases; this file only covers the rules agents must
not violate.

## Verification gate (run before every PR)

CI runs exactly this; reproduce it locally:

```bash
ruff check src tests tools
mypy src/audiobard
pytest --cov=audiobard --cov-fail-under=70 -m "not integration"
python tools/guards.py
```

## Hard rules

- **Never edit a versioned prompt in place** (`src/audiobard/llm/prompts.py`,
  `PROMPT_V*`). Add a new version and switch the default. Any prompt or
  parser change requires benchmark output with no regression
  (`audiobard benchmark --llm ollama --model qwen2.5:7b`) — see
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **`tools/guards.py` is a contract, not lint.** Its allowlists
  (`REQUIRED_IGNORE_RULES`, `ALLOWED_IGNORE_NEGATIONS`,
  `ALLOWED_DATA_BOOK_FILES`, `SECRET_EXEMPT_PATHS`) are reviewed by hand.
  Do not add entries silently; changes to the guards and the files they
  protect belong in the same PR.
- **No secrets in code.** Keys come from `.env` (gitignored) or the
  environment. Never commit a literal key; never paste one into an issue
  or chat.
- **`data/books/` is for public-domain samples only.** Never commit
  copyrighted books, user uploads, or generated audio (`*.mp3`, `*.m4b`).
- **One change per PR.** Personal fork config (your AGENTS.md, local
  scripts) never enters a PR.
- **Skeleton note (2026-08):** the repo is at Phase 1 (package skeleton +
  Pydantic contracts + CLI smoke, tests green). `src/audiobard/llm`,
  `tts`, `parser`, `audio` do not exist yet — do not assume interfaces
  beyond the Pydantic contracts in `src/audiobard/models.py`.

## Pointers

- Architecture/phases/ethics: `AudioBard_DevPlan.md`
- Contribution bar and precedents: `CONTRIBUTING.md`
- Security policy and threat model: `SECURITY.md`
- Pydantic contracts: `src/audiobard/models.py`
- Guard mechanics: `tools/guards.py` (self-documenting)