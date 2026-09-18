---
name: TTS / LLM Provider Proposal
about: Propose and implement a new TTS synthesis engine or LLM client for AudioBard
title: "[PROVIDER] Support for <Engine/Provider Name>"
labels: ["enhancement", "help wanted"]
assignees: ''
---

### 🧩 Proposed Engine / Provider
<!-- Name of the TTS engine or LLM provider (e.g. Kokoro TTS, Coqui, ElevenLabs, Claude, DeepSeek) -->

### ⚙️ Architecture & Category
- [ ] Neural TTS Engine (`TTSProvider` interface)
- [ ] LLM Client (`LLMClient` interface)

### 🔌 Provider Details
<!--
- Offline / Local (e.g. ONNX runtime, local weights) OR Cloud API (BYOK)
- Performance / latency expectations
- License of underlying models / APIs
-->

### 📋 Implementation Checklist
- [ ] Implement provider interface in `src/audiobard/tts/` or `src/audiobard/llm/`
- [ ] Add configuration settings in `src/audiobard/config.py`
- [ ] Add unit tests with pytest in `tests/`
- [ ] Add provider selector in Desktop GUI settings (`gui/src/components/SettingsModal.vue`)
- [ ] Update `README.md` and docs
