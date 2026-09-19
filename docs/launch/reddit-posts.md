# Reddit Launch Strategy & Copy Kit

> **Target Subreddits:** `r/LocalLLaMA`, `r/selfhosted`, `r/audiobooks`, `r/Python`, `r/tauri`

---

## 1. r/LocalLLaMA (Local Models & Open Source)

* **Post Type:** Text Post
* **Title:**  
  `I built AudioBard: An open-source multi-voice audiobook generator using Ollama + Piper TTS with a native Tauri v2 Desktop GUI`
* **Body:**

```text
Hey r/LocalLLaMA!

I wanted to share an open-source project I've been building that combines local LLMs with neural TTS to solve the single-voice monotone audiobook problem:

**AudioBard**: https://github.com/oscarbol09/audiobard

### How it works with local models:
1. **EPUB/TXT Ingestion:** Extracts paragraphs and clean dialogue structures.
2. **Character & Dialog Attribution:** Runs through Ollama (tested with `qwen2.5:7b` and `llama3.3:70b`) to extract cast members, track aliases, and attribute every dialogue line to its speaker with emotional context.
3. **Voice Casting:** Automatically matches character profiles (gender, age, tone) to available Piper neural TTS voices.
4. **Offline Synthesis:** Uses Piper TTS on CPU to synthesize each line and assemble full MP3/M4B audiobooks with chapter tags.

It features a native **Desktop GUI** built with Tauri v2 + Vue 3 (drag-and-drop book upload, library player, Spanish / English localization, BYOK cloud fallback if on a laptop without GPU) and a full **CLI**.


100% free, MIT licensed, zero telemetry.

Would love feedback from fellow local AI tinkerers!
```

---

## 2. r/selfhosted (Self-Hosted & Offline Tools)

* **Post Type:** Text Post
* **Title:**  
  `AudioBard – Self-hosted & offline multi-voice audiobook generator (Turn EPUBs into cast-narrated audiobooks)`
* **Body:**

```text
Hi r/selfhosted!

If you have a library of DRM-free or public-domain EPUBs and want to turn them into audiobooks without paying subscription fees to Audible or ElevenLabs, check out **AudioBard**:

Repo: https://github.com/oscarbol09/audiobard

### Key Highlights:
- **Multi-Voice Casting:** Doesn't just read the book with one voice — assigns distinct voices to each character based on dialogue attribution.
- **100% Offline Capability:** Runs completely on your hardware with Ollama + Piper TTS. No internet required.
- **Desktop App + CLI:** Native Tauri desktop application and CLI tool.
- **BYOK Cloud Fallback:** Supports NVIDIA NIM, OpenRouter, and Google Gemini if you prefer cloud APIs with your own keys.

It's MIT licensed and free forever. Hope you find it useful!
```

---

## 3. r/audiobooks (Audiobook Enthusiasts)

* **Post Type:** Text Post
* **Title:**  
  `I built a free tool to generate multi-voice audiobooks from EPUBs with different character voices (AudioBard)`
* **Body:**

```text
Hello audiobook lovers!

Standard text-to-speech readers are usually exhausting to listen to because they read both narration and dialogue in the exact same voice.

I built **AudioBard** (https://github.com/oscarbol09/audiobard) to fix this: it automatically parses your EPUB books, identifies who is speaking in each chapter, assigns different character voices, and produces full audiobooks with chapter markers.

You can run it as a desktop app with a simple drag-and-drop interface, and it costs nothing.

Check it out on GitHub and let me know what classics you'd like to hear!
```
