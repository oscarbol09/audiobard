# DEV.to / Hashnode Announcement Article

> **Target Platforms:** [DEV.to](https://dev.to) & [Hashnode](https://hashnode.com)  
> **Tags:** `python`, `tauri`, `opensource`, `audio`

---

```markdown
---
title: "How I Built an Open-Source Multi-Voice Audiobook Generator with Ollama, Piper, and Tauri"
published: true
description: "Turn EPUB and TXT books into full multi-voice audiobooks with distinct character voices. 100% offline, free, and open-source."
tags: python, tauri, opensource, audio
cover_image: https://raw.githubusercontent.com/oscarbol09/audiobard/main/assets/banner.svg
canonical_url: https://github.com/oscarbol09/audiobard
---

Reading classics is one of life's greatest pleasures, but finding hours of quiet time to sit with a physical book is tough. While audiobooks are wonderful, standard TTS readers (like Calibre's read-aloud or basic speech synthesizers) suffer from one fatal flaw: **they narrate the entire book in a single, monotonous voice.**

Commercial voice platforms can generate multi-voice audio, but they are closed-source, proprietary, and charge prohibitive subscription fees.

That's why I built **AudioBard** — an open-source, local-first multi-voice audiobook generator.

![AudioBard Pipeline](https://raw.githubusercontent.com/oscarbol09/audiobard/main/assets/demo-pipeline.svg)

---

## The Architecture: How AudioBard Works

AudioBard breaks audiobook production into a modular 5-step pipeline:

### 1. Ingestion & Semantic Parsing
Parses EPUB and TXT files, extracting chapters and paragraphs while preserving dialogue punctuation (quotes, em-dashes `—`, guillemets `«»`).

### 2. Character & Alias Extraction (LLM)
An LLM analyzes the cast:
- Identifies main and secondary characters (e.g. `Sherlock Holmes`, `Holmes`, `The Detective`).
- Assigns traits: gender, estimated age, and vocal tone (gruff, cheerful, melancholic).

### 3. Dialogue Attribution
The pipeline chunks text and prompts the LLM to determine who speaks each line and with what emotion.

### 4. Neural Voice Mapping
Maps extracted character profiles to a library of neural TTS voices (via Piper TTS or Microsoft Edge TTS), ensuring each character retains a consistent, distinct voice across all chapters.

### 5. Audio Assembly & Tagging
Synthesizes speech per line and uses `ffmpeg` / `pydub` to stitch the final MP3 or M4B audio file with embedded chapter metadata and cover art.

---

## Offline with Ollama & Piper TTS

One of my core design goals was **zero cloud dependency**:
- **Local LLM:** Works with [Ollama](https://ollama.com) running `qwen2.5:7b` or `llama3.3:70b`.
- **Local TTS:** Uses [Piper TTS](https://github.com/rhasspy/piper) — a neural text-to-speech engine optimized for fast CPU inference.

If you are on a lightweight laptop without a dedicated GPU, AudioBard also supports **Cloud BYOK** (Bring Your Own Key) using NVIDIA NIM, OpenRouter, or Google Gemini + Edge TTS.

---

## Native Desktop GUI (Tauri v2 + Vue 3)

AudioBard includes a desktop application built with Tauri v2 and Vue 3:
- Drag & Drop EPUB upload
- Instant English / Spanish language switcher
- Settings modal for BYOK API keys and voice selection
- Built-in audiobook player library

---

## Try It Out

- **GitHub Repository:** [github.com/oscarbol09/audiobard](https://github.com/oscarbol09/audiobard)
- **License:** MIT (Free & Open-Source)
```
