# Hacker News Launch Guide: "Show HN" 🚀

> **Target Platform:** [news.ycombinator.com](https://news.ycombinator.com/)  
> **Best Timing:** Tuesday or Wednesday between 08:00 AM – 10:00 AM ET.  
> **Format:** Link post submission + immediate first comment by author.

---

## 1. Submission Details

* **Title:**  
  `Show HN: AudioBard – Open-source multi-voice audiobook generator (Tauri GUI + Ollama/Piper)`
* **URL:**  
  `https://github.com/oscarbol09/audiobard`

---

## 2. Author's First Comment (Post immediately after submitting)

```text
Hi HN! I built AudioBard because I love reading classics, but wanted an audiobook player that narrates dialogue with distinct, tone-aware voices for each character — without being locked into expensive cloud APIs or monthly subscriptions.

Most TTS tools read entire books in a single robotic monotone voice, or require uploading your personal files to proprietary cloud platforms like ElevenLabs ($50+/mo).

AudioBard is a local-first, open-source audiobook generator with both a Desktop GUI (Tauri v2 + Vue 3) and a CLI:

How it works:
1. Ingest: Parses EPUB and TXT files, cleanly extracting chapter structures and paragraphs.
2. Character Extraction & Casting: Uses an LLM to identify the cast of characters, their aliases, genders, age ranges, and emotional tones.
3. Dialog Attribution: Analyzes dialogue context line-by-line to determine who speaks each line and with what emotion.
4. Neural Voice Mapping: Automatically maps distinct neural voices to each character (filtered by gender, tone, and accent).
5. Synthesis & Assembly: Synthesizes speech using neural Piper TTS (or Microsoft Edge TTS) and stitches final MP3/M4B audiobooks with chapter metadata.

Two execution modes:
- 100% Offline: Ollama (Qwen 2.5 / Llama 3.3) + Piper TTS (fast, CPU-only neural synthesis). Zero data leaves your machine.
- Cloud BYOK: Use NVIDIA NIM, OpenRouter, or Google Gemini with your own API keys + Edge TTS for low-resource machines.

The project is written in Python + Rust/Tauri, MIT licensed, and includes a full evaluation benchmark suite against gold-standard dialogue datasets.

GitHub: https://github.com/oscarbol09/audiobard

I'd love feedback from the HN community on dialogue attribution heuristics, local TTS quality, and ideas for expanding voice models!
```
