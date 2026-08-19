# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The changelog is an entry point for humans: every PR that changes behavior
adds an entry under the relevant section, in the same commit as the change.

## [Unreleased]

### Added

- Package skeleton (Phase 1): `pyproject.toml` (PEP 621), `src/audiobard`
  with a minimal typer CLI (`audiobard --version`), `py.typed`, and the
  Pydantic contracts that will drive the LLM JSON schemas (`Paragraph`,
  `Character`, `CharactersResult`, `DialogLine`, `AttributionResult`,
  `Voice`, `VoiceAssignment`) — 12 unit tests.
- CI workflow (`.github/workflows/ci.yml`): ruff + mypy (strict) lint job,
  pytest matrix on Python 3.10/3.11/3.12 with a 70% coverage gate,
  security guards job, and dependency-review on PRs. Actions pinned to
  commit SHAs, `permissions: contents: read`.
- Security and data-hygiene guards (`tools/guards.py`): fail CI on literal
  API keys in tracked source files, on missing/weakened personal-data
  gitignore rules, on non-allowlisted files under `data/books/`, and on
  tracked audio output — with tests that break one thing at a time.
- Rewritten `.gitignore` grouped by section (Python, secrets, data, audio,
  models, IDE/OS, logs, caches).

### Changed

- Rewritten README with project story, pipeline diagram, quick start,
  command reference, extension model, and ethics notes.
- Rewritten CONTRIBUTING: one-change-per-PR bar, evidence rules from real
  precedents (real input, reproducibility through the real code path,
  first-filed-with-tests wins, no personal fork config), benchmark bar for
  prompt/parser changes, guards contract section.

### Fixed

- (none yet)

### Security

- Added `SECURITY.md` with an honest threat model: user book data staying
  local, secrets/keys handling, prompt-injection containment via strict
  schema parsing — and the explicit out-of-scope trade-offs (malicious
  local providers, content filtering, cloud TOS, dependency supply chain).
- Discord notifier bot (`notifications.yml`) and its README; webhook URL
  lives in the `DISCORD_WEBHOOK_URL` secret, never in the repo.
- GitHub community files: issue/PR templates, code of conduct, branch
  protection on `main` (1 approving review, linear history).