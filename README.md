# AudioBard

> AI-powered audiobook generator with multi-character voice synthesis.
> **100% free, FOSS-first, offline-capable.**

AudioBard converts classic literary texts (public domain) into audiobooks by:

1. Parsing TXT/EPUB files
2. Detecting who speaks each line via a local LLM (Ollama)
3. Assigning unique, tone-aware voices to each character
4. Synthesizing audio with offline neural TTS (Piper)
5. Maintaining voice consistency across chapters

See [AudioBard_DevPlan.md](./AudioBard_DevPlan.md) for the full development plan.

## Status

🚧 **Pre-MVP** — repository scaffolded, development plan published. Implementation starts Week 1 of the plan.

## Quick start (planned for v0.1.0)

```bash
pip install audiobard[llm-ollama,tts-piper]
audiobard generate book.epub --output audiobook.mp3
```

## License

MIT — see [LICENSE](./LICENSE).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). All contributions require adherence to our [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## Ethics

Voice cloning without consent, DRM circumvention, and impersonation are explicitly out of scope. See §10 of the development plan.
