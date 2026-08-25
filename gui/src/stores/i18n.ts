import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useSettingsStore } from './settings'

const translations = {
  es: {
    // General / Header
    appTitle: 'AudioBard',
    subtitle: 'Conversor de Audiolibros Multivoz',
    settings: 'Configuración',
    language: 'Idioma',
    spanish: 'Español',
    english: 'Inglés',

    // Tabs
    tabUpload: 'Generar Audiolibro',
    tabLibrary: 'Mi Biblioteca',

    // Upload section
    dropTitle: 'Arrastra y suelta tu libro aquí',
    dropSubtitle: 'Formatos soportados: EPUB y TXT',
    selectFile: 'Seleccionar Archivo',
    generateBtn: 'Comenzar Conversión a Audiolibro',
    selectedBook: 'Libro Seleccionado:',

    // Settings Modal
    settingsTitle: 'Configuración de AudioBard',
    llmSection: 'Proveedor de Inteligencia Artificial (LLM)',
    llmProviderLabel: 'Proveedor LLM',
    ollamaHostLabel: 'Servidor Ollama (Local)',
    ollamaModelLabel: 'Modelo Ollama',
    byokTitle: 'BYOK — Trae tu propia API Key',
    apiKeyLabel: 'API Key',
    modelPresetLabel: 'Modelo seleccionado / Preset',
    customModelPlaceholder: 'O escribe un modelo personalizado...',
    ttsSection: 'Síntesis de Voz (TTS)',
    ttsProviderLabel: 'Motor de Voz',
    voiceLocaleLabel: 'Idioma de Voz',
    appearanceSection: 'Apariencia',
    themeLabel: 'Tema de Interfaz',
    themeSystem: 'Sistema',
    themeDark: 'Oscuro',
    themeLight: 'Claro',
    cacheSection: 'Almacenamiento y Caché',
    clearCacheBtn: 'Limpiar Caché de Audio y LLM',
    cacheCleared: '¡Caché limpiada con éxito!',
    outputFolderLabel: 'Carpeta de Salida de Audiolibros',
    browseBtn: 'Examinar...',
    resetDefaults: 'Restablecer Valores Predeterminados',
    closeBtn: 'Cerrar',

    // Generation Progress
    progressTitle: 'Generando Audiolibro...',
    cancelBtn: 'Cancelar Generación',
    cancelled: 'Generación cancelada por el usuario.',
    stageParsing: 'Analizando texto y capítulos...',
    stageAttribution: 'Atribuyendo diálogos y personajes con LLM...',
    stageVoice: 'Asignando voces a personajes...',
    stageSynthesis: 'Sintetizando clips de audio...',
    stageComplete: '¡Audiolibro completado!',

    // Library
    libraryTitle: 'Biblioteca de Audiolibros',
    noBooks: 'Aún no has generado audiolibros.',
    downloadBtn: 'Reproducir / Abrir Audio',
    regenerateBtn: 'Regenerar',

    // Providers
    providerOllama: 'Ollama (Local en tu PC)',
    providerOpenRouter: 'OpenRouter (Nube / BYOK)',
    providerGemini: 'Google Gemini (BYOK)',
    providerNim: 'NVIDIA NIM (BYOK - build.nvidia.com)',
  },
  en: {
    // General / Header
    appTitle: 'AudioBard',
    subtitle: 'Multi-Voice Audiobook Converter',
    settings: 'Settings',
    language: 'Language',
    spanish: 'Spanish',
    english: 'English',

    // Tabs
    tabUpload: 'Generate Audiobook',
    tabLibrary: 'My Library',

    // Upload section
    dropTitle: 'Drag and drop your book here',
    dropSubtitle: 'Supported formats: EPUB and TXT',
    selectFile: 'Select File',
    generateBtn: 'Start Audiobook Conversion',
    selectedBook: 'Selected Book:',

    // Settings Modal
    settingsTitle: 'AudioBard Settings',
    llmSection: 'Artificial Intelligence Provider (LLM)',
    llmProviderLabel: 'LLM Provider',
    ollamaHostLabel: 'Ollama Server (Local)',
    ollamaModelLabel: 'Ollama Model',
    byokTitle: 'BYOK — Bring Your Own Key',
    apiKeyLabel: 'API Key',
    modelPresetLabel: 'Selected Model / Preset',
    customModelPlaceholder: 'Or enter custom model name...',
    ttsSection: 'Speech Synthesis (TTS)',
    ttsProviderLabel: 'Voice Engine',
    voiceLocaleLabel: 'Voice Language',
    appearanceSection: 'Appearance',
    themeLabel: 'Interface Theme',
    themeSystem: 'System',
    themeDark: 'Dark',
    themeLight: 'Light',
    cacheSection: 'Storage & Cache',
    clearCacheBtn: 'Clear Audio & LLM Cache',
    cacheCleared: 'Cache cleared successfully!',
    outputFolderLabel: 'Audiobook Output Directory',
    browseBtn: 'Browse...',
    resetDefaults: 'Reset to Defaults',
    closeBtn: 'Close',

    // Generation Progress
    progressTitle: 'Generating Audiobook...',
    cancelBtn: 'Cancel Generation',
    cancelled: 'Generation cancelled by user.',
    stageParsing: 'Parsing text and chapters...',
    stageAttribution: 'Attributing dialog & characters with LLM...',
    stageVoice: 'Mapping character voices...',
    stageSynthesis: 'Synthesizing audio clips...',
    stageComplete: 'Audiobook complete!',

    // Library
    libraryTitle: 'Audiobook Library',
    noBooks: 'No audiobooks generated yet.',
    downloadBtn: 'Play / Open Audio',
    regenerateBtn: 'Regenerate',

    // Providers
    providerOllama: 'Ollama (Local on your PC)',
    providerOpenRouter: 'OpenRouter (Cloud / BYOK)',
    providerGemini: 'Google Gemini (BYOK)',
    providerNim: 'NVIDIA NIM (BYOK - build.nvidia.com)',
  },
}

export type TranslationKey = keyof typeof translations.es

export const useI18nStore = defineStore('i18n', () => {
  const settingsStore = useSettingsStore()

  const t = computed(() => {
    const lang = settingsStore.settings.language || 'es'
    return (key: TranslationKey): string => {
      return translations[lang]?.[key] || translations['es']?.[key] || key
    }
  })

  return { t }
})
