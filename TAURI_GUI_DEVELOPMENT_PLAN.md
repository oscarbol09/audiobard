# 🎯 AudioBard GUI - Plan de Desarrollo Tauri + Vue 3

## 📋 Visión General

Crear una aplicación de escritorio nativa, moderna y profesional para AudioBard que permita a los usuarios generar audiobooks sin tocar la consola.

**Stack:**
- **Frontend:** Vue 3 + TypeScript
- **Framework Desktop:** Tauri (Rust)
- **Backend:** Python FastAPI (existente + extendido)
- **Styling:** Tailwind CSS
- **Database:** SQLite (ya existe)

**Resultado Final:**
- Instalador profesional: `AudioBard-0.1.0-Setup.exe`
- Aplicación nativa de escritorio
- Biblioteca personal de audiobooks
- Historial de generaciones

---

## 🗓️ Timeline: 12 Semanas

### **Semana 1-2: Setup & Estructura Base**

**Objetivo:** Tener un proyecto Tauri corriendo localmente con Vue 3 configurado

**Deliverables:**
- [ ] Proyecto Tauri inicializado
- [ ] Vue 3 + Tailwind CSS configurado
- [ ] Estructura de carpetas lista
- [ ] IPC (comunicación Tauri ↔ Frontend) funcionando

**Tareas:**

```bash
# Crear proyecto Tauri
cargo install tauri-cli
cargo tauri init --ci

# Estructura final
audiobard/
├── src/                                    # Python core (sin cambios)
├── src-tauri/
│   ├── src/
│   │   ├── main.rs                        # Entry point Rust
│   │   └── commands/
│   │       ├── generate.rs                # Comando para generar
│   │       ├── library.rs                 # Comandos de biblioteca
│   │       └── settings.rs                # Comandos de settings
│   └── Cargo.toml
│
└── src/frontend/                          # Frontend Vue
    ├── src/
    │   ├── components/
    │   │   ├── UploadSection.vue
    │   │   ├── LibraryPanel.vue
    │   │   ├── GenerationProgress.vue
    │   │   ├── SettingsModal.vue
    │   │   └── PlayerWidget.vue
    │   ├── pages/
    │   │   ├── Home.vue
    │   │   └── Settings.vue
    │   ├── stores/                        # Pinia state management
    │   │   ├── books.ts
    │   │   ├── settings.ts
    │   │   └── generation.ts
    │   ├── App.vue
    │   └── main.ts
    ├── index.html
    └── package.json
```

**Milestones:**
- ✅ `npm run tauri dev` abre ventana
- ✅ Componente Vue simple renderiza
- ✅ Comando Rust → Frontend comunica

---

### **Semana 3-4: Componente Upload & Selector Idioma**

**Objetivo:** Interfaz visual para subir libros y elegir idioma/proveedor

**Deliverables:**
- [ ] Componente `UploadSection.vue` funcional
- [ ] Drag & drop funcionando
- [ ] Selector de idioma visual
- [ ] Selector de proveedores (LLM/TTS)
- [ ] Validación de archivos

**Features:**
```
UploadSection.vue
├── Drag & Drop (TXT/EPUB)
├── Click para seleccionar archivo
├── Vista previa del archivo seleccionado
├── Selector de idioma (dropdown)
│   ├── 🇬🇧 English (en_US)
│   ├── 🇪🇸 Español (es_ES)
│   ├── 🇫🇷 Français (fr_FR)
│   ├── 🇩🇪 Deutsch (de_DE)
│   └── 🇮🇹 Italiano (it_IT)
├── Selector de LLM provider
│   ├── Ollama (local)
│   ├── OpenRouter (cloud)
│   └── Gemini (cloud)
├── Selector de TTS provider
│   ├── Piper (local)
│   └── Edge TTS (cloud)
└── Botón "Generar"
```

**UI Mockup:**
```
┌─────────────────────────────────────┐
│ AudioBard v0.1.0                    │
├─────────────────────────────────────┤
│                                     │
│  ┌───────────────────────────────┐  │
│  │ 📄 Arrastra libro aquí        │  │
│  │    o haz click                │  │
│  │  Soporta: .txt, .epub         │  │
│  └───────────────────────────────┘  │
│                                     │
│  Idioma: [dropdown: Español      ] │
│  LLM:    [dropdown: Ollama       ] │
│  TTS:    [dropdown: Piper        ] │
│                                     │
│              [▶️ Generar]           │
│                                     │
└─────────────────────────────────────┘
```

**Milestones:**
- ✅ Subir archivo
- ✅ Seleccionar idioma
- ✅ Validación de archivo

---

### **Semana 5-6: Integración con Pipeline Python**

**Objetivo:** Conectar frontend con el pipeline de AudioBard

**Deliverables:**
- [ ] FastAPI creado para exponer pipeline
- [ ] Endpoint `POST /generate` funcionando
- [ ] Endpoint `GET /library` funcionando
- [ ] Comunicación Tauri ↔ FastAPI establecida
- [ ] Archivo sube correctamente al servidor Python

**Arquitectura:**
```
Frontend (Tauri)
    ↓ (IPC JSON-RPC)
Tauri Backend (Rust)
    ↓ (HTTP)
FastAPI (Python)
    ↓
AudioBookPipeline (existente)
    ↓
SQLite + archivos de caché
```

**Endpoints FastAPI necesarios:**

```python
# src/audiobard/api.py

@app.post("/generate")
async def generate(
    file: UploadFile,
    locale: str = "en_US",
    llm_provider: str = "ollama",
    tts_provider: str = "piper",
) -> dict:
    """Generar audiobook"""
    # Guardar archivo temporalmente
    # Ejecutar pipeline
    # Retornar info de generación

@app.get("/library")
async def get_library() -> list[dict]:
    """Obtener todos los libros generados"""

@app.get("/book/{book_id}")
async def get_book(book_id: int) -> dict:
    """Detalles de un libro"""

@app.get("/book/{book_id}/download")
async def download_book(book_id: int):
    """Descargar audiobook generado"""

@app.post("/book/{book_id}/regenerate")
async def regenerate_book(book_id: int) -> dict:
    """Regenerar audiobook reutilizando settings"""

@app.get("/voices")
async def get_voices(locale: str = "en_US") -> list[dict]:
    """Listar voces disponibles"""
```

**Milestones:**
- ✅ FastAPI corriendo en `localhost:8000`
- ✅ Frontend se comunica con API
- ✅ Archivo se procesa correctamente

---

### **Semana 7-8: Barra de Progreso & Historial**

**Objetivo:** Feedback visual durante generación y ver libros previos

**Deliverables:**
- [ ] Barra de progreso en tiempo real (WebSocket o polling)
- [ ] Componente `LibraryPanel.vue` mostrando libros generados
- [ ] Búsqueda/filtros en biblioteca
- [ ] Botón reutilizar audiobook existente

**Features:**
```
┌──────────────────────────────────────┐
│ Generando: Pride and Prejudice      │
│ [████████░░░░░░░░░░] 45%             │
│ Paso actual: Sintetizando voces      │
│ Tiempo restante: ~5 minutos          │
└──────────────────────────────────────┘

📚 MI BIBLIOTECA
┌────────────────────┬────────────────┐
│ Pride & Prejudice  │ Orgullo y...   │
│ 2,543 párafos      │ 1,892 párafos  │
│ [🔄 Regenerar]     │ [🔄 Regenerar] │
│ [▶️ Reproducir]    │ [▶️ Reproducir]│
└────────────────────┴────────────────┘
```

**Milestones:**
- ✅ Progreso actualiza en tiempo real
- ✅ Lista de libros carga desde DB
- ✅ Búsqueda funciona

---

### **Semana 9: Reproductor Integrado**

**Objetivo:** Escuchar previsualizaciones sin salir de la app

**Deliverables:**
- [ ] Componente `PlayerWidget.vue`
- [ ] Controles: play/pause/volumen/progreso
- [ ] Integración con archivo MP3/M4B

**Features:**
```
┌──────────────────────────────────────┐
│ 🎵 Pride and Prejudice               │
│ [▶️ ⏸ ⏹] [════════░░░░░] 2:34 / 8:45│
│ Volumen: [████████░░░░░░] 75%        │
│ Velocidad: [1.0x ▼]                  │
└──────────────────────────────────────┘
```

**Milestones:**
- ✅ Reproducir audiobook
- ✅ Controles de audio funcionan

---

### **Semana 10-11: Settings & Pulida de UI**

**Objetivo:** Configuración avanzada y experiencia profesional

**Deliverables:**
- [ ] Modal de Settings
- [ ] Guardar preferencias por usuario
- [ ] Temas (claro/oscuro)
- [ ] Iconos profesionales
- [ ] Animaciones suave
- [ ] Handling de errores robusto

**Settings disponibles:**
```
⚙️ CONFIGURACIÓN

LLM Provider
└─ [Ollama      ▼] Modelo: qwen2.5:7b
└─ [OpenRouter  ▼] API Key: ••••••••
└─ [Gemini      ▼] API Key: ••••••••

TTS Provider
└─ [Piper       ▼]
└─ [Edge TTS    ▼]

Apariencia
└─ Tema: [Light / Dark]
└─ Idioma UI: [Español ▼]

Caché
└─ Tamaño: 2.3 GB
└─ [Limpiar caché]

Rutas
└─ Carpeta de salida: /home/user/AudioBooks
└─ [Cambiar...]
```

**Milestones:**
- ✅ UI profesional y responsive
- ✅ Themes funcionan
- ✅ Settings se guardan

---

### **Semana 12: Empaquetado & Distribución**

**Objetivo:** Crear instalador profesional

**Deliverables:**
- [ ] Build de producción
- [ ] Generador NSIS (Windows installer)
- [ ] Icono profesional
- [ ] Ejecutable firmado (opcional)
- [ ] Documentación de instalación
- [ ] Release en GitHub

**Build commands:**
```bash
# Development
npm run tauri dev

# Production
npm run tauri build

# Resultado:
# → src-tauri/target/release/AudioBard.exe
# → AudioBard_0.1.0_x64-setup.exe (con NSIS)
# → AudioBard.msi (si usas wix)
```

**Milestones:**
- ✅ `.exe` instalable
- ✅ App funciona post-instalación
- ✅ Release v0.1.0 publicado

---

## 🔄 Arquitectura Técnica Detallada

### Tauri Commands (Rust ↔ Frontend)

```rust
// src-tauri/src/commands/generate.rs
#[tauri::command]
async fn generate_audiobook(
    book_path: String,
    locale: String,
    llm_provider: String,
    tts_provider: String,
) -> Result<GenerationResponse, String> {
    // 1. Validar archivo
    // 2. Llamar API Python
    // 3. Retornar resultado
}

#[tauri::command]
async fn get_library() -> Result<Vec<Book>, String> {
    // Consultar SQLite vía FastAPI
}

#[tauri::command]
async fn cancel_generation() -> Result<(), String> {
    // Cancelar generación en curso
}
```

### FastAPI Python

```python
# src/audiobard/api.py
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import asyncio
from pathlib import Path

app = FastAPI(title="AudioBard API", version="0.1.0")

@app.post("/generate")
async def generate(
    file: UploadFile,
    locale: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """Genera audiobook en background"""
    book_path = Path(f"/tmp/{file.filename}")
    
    # Guardar archivo
    content = await file.read()
    book_path.write_bytes(content)
    
    # Iniciar generación en background
    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        run_generation,
        task_id=task_id,
        book_path=book_path,
        locale=locale,
    )
    
    return {"task_id": task_id, "status": "processing"}

@app.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """Obtener estado de tarea"""
    # Retornar: {"status": "processing", "progress": 45}
    # O: {"status": "completed", "result": {...}}

@app.get("/library")
async def get_library() -> list[dict]:
    """Obtener biblioteca personal"""
    persistence = PersistenceManager(...)
    books = persistence.get_all_books()
    return [
        {
            "id": book.id,
            "title": book.title,
            "path": str(book.path),
            "created_at": book.created_at,
            "duration_minutes": book.duration_minutes,
        }
        for book in books
    ]
```

### Pinia Store (Estado Frontend)

```typescript
// src/frontend/src/stores/generation.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const currentFile = ref<File | null>(null)
  const progress = ref(0)
  const progressMessage = ref('')
  const error = ref<string | null>(null)
  
  const startGeneration = async (file: File, locale: string) => {
    isGenerating.value = true
    error.value = null
    currentFile.value = file
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('locale', locale)
      
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        body: formData,
      })
      
      const data = await response.json()
      // Polling o WebSocket para progreso
      await pollProgress(data.task_id)
      
    } catch (err) {
      error.value = String(err)
    } finally {
      isGenerating.value = false
    }
  }
  
  return {
    isGenerating,
    currentFile,
    progress,
    progressMessage,
    error,
    startGeneration,
  }
})
```

---

## 📦 Dependencias Necesarias

### Rust (Cargo.toml)
```toml
[dependencies]
tauri = { version = "1.x", features = ["shell-open"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
reqwest = { version = "0.11", features = ["json"] }
```

### Node.js (package.json)
```json
{
  "dependencies": {
    "vue": "^3.x",
    "pinia": "^2.x",
    "axios": "^1.x"
  },
  "devDependencies": {
    "typescript": "^5.x",
    "@vitejs/plugin-vue": "^4.x",
    "tailwindcss": "^3.x",
    "@tauri-apps/api": "^1.x"
  }
}
```

### Python (pyproject.toml - adicional)
```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.104",
    "uvicorn>=0.24",
    "python-multipart>=0.0.6",
    "aiofiles>=23.0",
]
```

---

## 🎯 Criterios de Éxito

### Semana 2 (Setup)
- ✅ Proyecto Tauri corriendo
- ✅ Vue 3 renderizando
- ✅ Comunicación IPC funcionando

### Semana 4 (UI Upload)
- ✅ Upload drag & drop
- ✅ Selector idioma visible
- ✅ Botón Generar presente

### Semana 6 (Pipeline)
- ✅ Archivo sube a servidor
- ✅ Pipeline ejecuta correctamente
- ✅ Archivo de salida se genera

### Semana 8 (Historial)
- ✅ Biblioteca muestra libros
- ✅ Búsqueda filtra correctamente
- ✅ Reutilización funciona

### Semana 11 (Pulida)
- ✅ UI profesional
- ✅ Sin errores no manejados
- ✅ Responsive en diferentes resoluciones

### Semana 12 (Release)
- ✅ Instalador `.exe` funciona
- ✅ App corre sin problemas post-instalación
- ✅ v0.1.0 publicado en GitHub

---

## 🐛 Riesgos & Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|--------|-----------|
| Integración Tauri-Python compleja | Media | Alto | Empezar con FastAPI en semana 5 |
| Performance del pipeline lenta | Baja | Medio | WebWorkers / threading en Rust |
| UI responsive en resolutions pequeñas | Media | Bajo | Testing con Tailwind breakpoints |
| Compilación Rust toma mucho tiempo | Baja | Bajo | Cache de Cargo, CI temprano |
| Base de datos SQLite se corrompe | Muy baja | Alto | Backups automáticos, validación |

---

## ✅ Checklist de Inicio

Antes de empezar semana 1:

- [ ] Rust instalado (`rustup`)
- [ ] Node.js 18+ instalado
- [ ] Python 3.10+ con `audiobard` instalado
- [ ] Rama `feature/tauri-gui` creada
- [ ] README actualizado con instrucciones de setup

---

## 📚 Recursos

- **Tauri Docs:** https://tauri.app/v1/guides/
- **Vue 3 Guide:** https://vuejs.org/guide/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Tailwind CSS:** https://tailwindcss.com/docs

---

**Autor:** AudioBard Development Plan  
**Versión:** 1.0  
**Última actualización:** 2026-08-23
