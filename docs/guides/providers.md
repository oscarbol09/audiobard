# Supported Providers

AudioBard supports a variety of local offline backends and cloud BYOK (Bring Your Own Key) providers.

---

## LLM Providers (Character Extraction & Attribution)

| Provider | Type | Privacy | Recommended Models | Environment Variable |
| :--- | :--- | :--- | :--- | :--- |
| **Ollama** | Local / Offline | 100% Private | `qwen2.5:7b`, `llama3.3:70b` | None (Local host) |
| **Google Gemini** | Cloud BYOK | Cloud | `gemini-2.0-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY` |
| **NVIDIA NIM** | Cloud BYOK | Cloud | `meta/llama-3.3-70b-instruct` | `NVIDIA_API_KEY` |
| **OpenRouter** | Cloud BYOK | Cloud | `anthropic/claude-3.5-haiku` | `OPENROUTER_API_KEY` |

### Configuring Ollama (Offline Default)
Ensure Ollama is running locally:
```bash
ollama run qwen2.5:7b
```

### Configuring Cloud API Keys
Add your keys to a `.env` file in the repository root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
NVIDIA_API_KEY=your_nvidia_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

---

## TTS Providers (Voice Synthesis)

| Provider | Type | Privacy | Highlights |
| :--- | :--- | :--- | :--- |
| **Piper TTS** | Local / Offline | 100% Private | Ultra-fast CPU neural synthesis, zero latency, lightweight ONNX models. |
| **Edge TTS** | Cloud (Free) | Cloud | High-fidelity neural voices with diverse regional accents and prosody support. |

---

## Configuration File (`config.yaml`)

You can persist your default provider selections in `config.yaml`:

```yaml
llm:
  provider: ollama        # ollama | gemini | openrouter | nim
  model: qwen2.5:7b
  temperature: 0.1

tts:
  provider: piper         # piper | edge
  locale: en_US

audio:
  format: mp3             # mp3 | m4b
  bitrate: 192k
  silence_gap_ms: 300
  normalize_volume: true
```
