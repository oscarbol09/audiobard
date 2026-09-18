# Quickstart ⚡

Get started with AudioBard in less than 5 minutes using either the GUI or the CLI.

---

## 🖥️ Method A: Desktop GUI

1. Launch AudioBard:
   ```bash
   cargo tauri dev
   ```
2. **Drag and Drop:** Drop your `.epub` or `.txt` book onto the upload zone.
3. **Review Cast:** AudioBard extracts the character roster and proposes voice assignments. You can customize any character's voice or emotional pitch.
4. **Generate:** Click **Generate Audiobook**.
5. **Listen:** Play the resulting multi-voice audio directly in the built-in Library player or export as `.mp3`.

---

## 💻 Method B: Command Line Interface (CLI)

### 1. Basic Generation
Convert an EPUB or TXT file into a multi-voice audiobook:
```bash
audiobard generate book.epub --output audiobook.mp3
```

### 2. Dry-Run Mode (Test Attribution Without Audio Synthesis)
If you want to rapidly iterate on LLM prompts or inspect character attribution without waiting for TTS synthesis:
```bash
audiobard generate book.epub --dry-run
```

### 3. Listing Available Voices
Inspect available neural voices for a specific language/locale:
```bash
audiobard voices --locale en_US
audiobard voices --locale es_ES
```

### 4. Inspecting Cache & Statistics
Check your disk cache hit rate and saved synthesis time:
```bash
audiobard stats
```
