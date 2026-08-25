# AudioBard Desktop GUI (Vue 3 + TypeScript + Pinia + Tailwind CSS)

The official desktop frontend for AudioBard, powered by **Vue 3**, **Tauri v2**, **Pinia**, and **Tailwind CSS**.

## Features

- 📄 **Drag-and-Drop Book Upload**: Drop `.epub` or `.txt` files directly onto the interface.
- 🌐 **Multi-Language (i18n)**: Reactive switching between **Spanish (🇪🇸)** and **English (🇺🇸)** via `useI18nStore`.
- 🔑 **BYOK (Bring Your Own Key) Settings Modal**:
  - Configure **NVIDIA NIM** (`build.nvidia.com`), **OpenRouter**, **Google Gemini**, and **Ollama**.
  - Custom model preset pickers and custom model text inputs.
  - Native output folder browser and cache cleaner integration.
- ⚡ **Real-Time Progress Feedback**: Progress bar polling synthesis updates from the Python FastAPI sidecar.
- 📚 **Personal Audiobook Library**: Search, listen, or regenerate existing audiobooks.

## Project Structure

```
gui/
├── src/
│   ├── components/
│   │   ├── UploadSection.vue         # Drag & drop file picker
│   │   ├── GenerationProgress.vue    # Progress bar & cancel button
│   │   ├── LibraryPanel.vue          # Bookshelf list & playback
│   │   └── SettingsModal.vue         # BYOK, model & theme settings
│   ├── stores/
│   │   ├── generation.ts             # Pinia store for conversion pipeline
│   │   ├── settings.ts               # Pinia store for persisted app settings
│   │   └── i18n.ts                   # Pinia store for Spanish/English translations
│   ├── App.vue                       # Top level layout & health check overlay
│   └── main.ts                       # App bootstrapper
├── package.json
└── vite.config.ts
```

## Development Commands

Run from project root or `gui/` directory:

```bash
# Type check Vue SFCs without emitting JS
npx vue-tsc --noEmit

# Build production bundle
npm run build

# Development mode via Tauri
cargo tauri dev
```
