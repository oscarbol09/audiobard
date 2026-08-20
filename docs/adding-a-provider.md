# Adding a Provider to AudioBard

AudioBard is designed with an anti-fragile, pluggable architecture. All external engines (LLM providers, TTS synthesis engines, and book parsers) are hidden behind abstract base classes.

---

## 1. Adding a new LLM Provider

To add a new LLM provider (e.g. Anthropic, Mistral, LocalAI):

1. **Subclass `LLMClient`** in `src/audiobard/llm/<provider>_client.py`:
   ```python
   from audiobard.llm.base import LLMClient
   from typing import Any

   class CustomLLMClient(LLMClient):
       def __init__(self, model: str = "default-model", **kwargs: Any) -> None:
           super().__init__(model=model, **kwargs)

       async def _raw_call(self, prompt: str, schema: dict[str, Any]) -> str:
           # Call provider API with JSON constrained schema
           ...
           return raw_json_string
   ```

2. **Register the provider** in `src/audiobard/pipeline.py`:
   - Update `create_llm_client(config, persistence)` factory to recognize the new provider identifier.
   - Update `AudioBardConfig.llm_provider` type annotations in `src/audiobard/config.py`.

3. **Declare Optional Dependencies**:
   - Add extra dependencies to `[project.optional-dependencies]` in `pyproject.toml`.

4. **Add Unit Tests**:
   - Add unit tests with mock HTTP responses (using `respx` or `unittest.mock`) in `tests/test_llm_<provider>.py`.

---

## 2. Adding a new TTS Provider

To add a new TTS provider (e.g. Coqui TTS, Kokoro, ElevenLabs):

1. **Subclass `TTSProvider`** in `src/audiobard/tts/<provider>_provider.py`:
   ```python
   from audiobard.tts.base import TTSProvider
   from audiobard.models import Voice, Emotion

   class CustomTTSProvider(TTSProvider):
       async def _synthesize_raw(
           self,
           text: str,
           voice: Voice,
           emotion: Emotion,
           rate: float,
           pitch: float,
       ) -> bytes:
           # Synthesize audio and return raw MP3 bytes
           ...
           return mp3_bytes

       async def list_voices(self, locale: str) -> list[Voice]:
           # Return available Voice models for locale
           ...
           return [Voice(id="voice-id", locale=locale, ...)]
   ```

2. **Inherent Caching & Rate Limiting**:
   - `TTSProvider` automatically handles in-memory LRU caching (500 MB limit) and disk caching in `~/.cache/audiobard/tts/`.
   - Concurrency is automatically throttled by the provider semaphore (`config.tts_semaphore`).

3. **Register the Provider**:
   - Update `create_tts_provider(config)` factory in `src/audiobard/pipeline.py`.
   - Add the option to `AudioBardConfig.tts_provider`.

4. **Add Unit Tests**:
   - Test synthesis arguments and voice listing in `tests/test_tts_<provider>.py`.
