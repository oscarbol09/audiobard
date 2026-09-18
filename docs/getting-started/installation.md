# Installation Guide 📦

AudioBard can be used as a Python CLI tool or as a native Desktop GUI application.

---

## 📋 Prerequisites

Before installing AudioBard, ensure you have the following tools installed on your operating system:

| Tool | Required For | Recommended Version | Download Link |
| :--- | :--- | :--- | :--- |
| **Python** | Core Engine & CLI | Python 3.10 – 3.12 | [python.org](https://www.python.org/downloads/) |
| **FFmpeg** | Audio assembly & export | Latest stable | [ffmpeg.org](https://ffmpeg.org/download.html) |
| **Ollama** | Local offline LLM (optional) | Latest | [ollama.com](https://ollama.com/) |
| **Piper TTS** | Local offline voice synthesis | Latest | [github.com/rhasspy/piper](https://github.com/rhasspy/piper) |
| **Node.js & Rust** | Building Desktop GUI from source | Node 18+, Rust 1.75+ | [rust-lang.org](https://www.rust-lang.org/) |

---

## 🐍 CLI & Python Package Setup

### 1. Clone the repository
```bash
git clone https://github.com/oscarbol09/audiobard.git
cd audiobard
```

### 2. Create and activate a virtual environment
=== "Linux / macOS"
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
=== "Windows (PowerShell)"
    ```powershell
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    ```

### 3. Install AudioBard with optional provider extras
```bash
# Full local offline setup (Ollama + Piper + dev tools)
pip install -e ".[dev,llm-gemini,llm-ollama,tts-piper]"
```

---

## 🩺 Verifying Your Environment

AudioBard includes a built-in diagnostic tool that tests your system dependencies, audio codecs, model accessibility, and cache status:

```bash
audiobard doctor
```

Output should show green checkmarks for Python, FFmpeg, Ollama connectivity, and available Piper models.

---

## 🖥️ Desktop GUI Setup (Tauri v2 + Vue 3)

To run or build the desktop app locally:

```bash
# 1. Install frontend dependencies
cd gui
npm install
cd ..

# 2. Launch Desktop GUI in development mode
cargo tauri dev

# 3. Build standalone production installer (.exe / .msi / .dmg / .AppImage)
cargo tauri build
```
