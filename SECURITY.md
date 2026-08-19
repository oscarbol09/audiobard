# Security Policy

AudioBard runs **third-party code on your machine**: local LLM runtimes
(Ollama, LM Studio), local TTS engines (Piper), and remote LLM/TTS providers
whose SDKs are executed inside this package. It also reads your book files.
That combination deserves an honest threat model, not a generic template.

## Supported versions

Only the `main` branch is supported. There are no releases yet; pin your
install to a commit if you run AudioBard in a scripted context.

## Reporting a vulnerability

- **Report privately, not in issues.** Issues are public and the project is
  in its earliest stage — do not burn a disclosure window on a public
  tracker. Email the maintainer or open a private fork-based report; a
  GitHub security advisory will be opened once there is anything to
  coordinate around.
- A useful report includes: the versions involved (`pip show audiobard`,
  provider versions), the exact command or config that reproduces it, and
  what an attacker with which privileges would gain. Non-reproducible
  reports are triaged last.

## Threat model

Who we protect, against what, and what we explicitly do not defend:

### In scope

1. **User book data.** Books may be private or copyrighted. They must stay
   on the user's machine: AudioBard must not upload them anywhere except to
   an explicitly configured provider endpoint, and never silently. The
   `tools/guards.py` CI job pins gitignore rules that keep books and
   generated audio out of the repository, and blocks literal API keys in
   tracked files.
2. **Secrets and keys.** Provider API keys (Gemini, OpenRouter, NVIDIA,
   Piper downloads, optional TTS cloud keys) are loaded from `.env` or the
   environment, never hardcoded. CI fails on hardcoded keys. Key material
   must not end up in logs, issue reports, or `data/` output.
3. **Prompt-injection containment.** LLM-provided output is parsed with
   strict, validated schemas (Pydantic). A malicious book could try to
   inject instructions into the extraction or dialog-attribution step. We
   contain this by (a) parsing provider output as data, not instructions;
   (b) never echoing provider output into new provider prompts as
   instructions; (c) `make_audiobook.py` operating on the parsed contract,
   not on raw book text. Defense in depth: users should still review the
   attribution map once before generating (the CLI prints it).

### Out of scope (and why)

1. **Malicious providers.** A compromised Ollama endpoint, Piper build, or
   remote provider SDK executes arbitrary code with your user privileges by
   design. No wrapper can contain that; the practical mitigations are
   installing these from trusted sources and keeping them updated. We
   document this in the dev plan rather than pretend it away.
2. **LLM censorship/abuse filtering.** The voices and text synthesis are
   intentionally unfiltered (see the ethics note in the README). A request
   to suppress specific content types is a product decision, not a security
   feature; don't file it as a vulnerability.
3. **Cloud TOS violations.** Providers' terms (e.g. Gemini's non-commercial
   restriction for some models) are contractual matters for the user, not
   code defects.
4. **Supply-chain compromise of pinned dependencies.** CI pins actions to
   SHAs and runs `dependency-review` on PRs, but the Python dependency tree
   itself is resolved normally. Report a malicious package in our tree as a
   vulnerability (that is in scope as an integrity concern).

### Known hard trade-offs

- **`edge-tts` (optional preview).** It scrapes Microsoft's consumer
  endpoint without an API key. It can break or be blocked at any time, and
  it is ethically gray; it is not a supported backend for the benchmark and
  is opt-in only. Using it is the user's call.
- **Local model sizes.** Piper models and LLM runtimes can be large
  downloads from third-party mirrors; verify checksums where the mirror
  provides them.

## Configuration hygiene

- Put keys in `.env` (gitignored, pinned by guards) or the environment.
- Do not paste keys into issues or Discord notifications. The repo's
  Discord webhook carries issue titles/labels only; still, treat keys as
  private.
- `data/books/` is for public-domain samples you are willing to publish.
  Private books belong in a fork or a local directory outside the repo.

## Response process

Triaged in order: private reports first (same-day acknowledgment), then
security-labeled issues, then everything else. A confirmed in-scope issue
gets a fix on `main` plus a changelog entry; a security advisory is opened
when coordination with providers or users is needed.