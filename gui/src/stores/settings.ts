import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

type Theme = 'light' | 'dark' | 'system'
type LLMProvider = 'ollama' | 'gemini' | 'openrouter' | 'nim'
type TTSProvider = 'piper' | 'edge'
type Language = 'es' | 'en'

interface AppSettings {
  // Language & i18n
  language: Language

  // LLM Settings
  llmProvider: LLMProvider
  llmModel: string
  ollamaUrl: string
  ollamaModel: string
  geminiApiKey: string
  geminiModel: string
  openrouterApiKey: string
  openrouterModel: string
  nimApiKey: string
  nimModel: string

  // TTS Settings
  ttsProvider: TTSProvider
  ttsLocale: string
  piperVoice: string
  edgeVoice: string

  // Appearance
  theme: Theme

  // Cache
  maxCacheSizeGB: number

  // Output
  outputFolder: string
}

export const DEFAULT_LOCALE_EDGE_VOICES: Record<string, string> = {
  es_MX: 'es-MX-JorgeNeural',
  es_CO: 'es-CO-GonzaloNeural',
  es_ES: 'es-ES-AlvaroNeural',
  en_US: 'en-US-JennyNeural',
  fr_FR: 'fr-FR-HenriNeural',
  de_DE: 'de-DE-ConradNeural',
  it_IT: 'it-IT-DiegoNeural',
}

const DEFAULT_SETTINGS: AppSettings = {
  language: 'es',
  llmProvider: 'openrouter',
  llmModel: 'nvidia/nemotron-3-ultra-550b-a55b:free',
  ollamaUrl: 'http://localhost:11434',
  ollamaModel: 'qwen2.5:7b',
  geminiApiKey: '',
  geminiModel: 'gemini-2.0-flash',
  openrouterApiKey: '',
  openrouterModel: 'nvidia/nemotron-3-ultra-550b-a55b:free',
  nimApiKey: '',
  nimModel: 'nvidia/llama-3.1-nemotron-70b-instruct',
  ttsProvider: 'edge',
  ttsLocale: 'es_MX',
  piperVoice: '',
  edgeVoice: 'es-MX-JorgeNeural',
  theme: 'dark',
  maxCacheSizeGB: 5,
  outputFolder: '',
}

const STORAGE_KEY = 'audiobard-settings'

export const useSettingsStore = defineStore('settings', () => {
  const loadSettings = (): AppSettings => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return { ...DEFAULT_SETTINGS, ...parsed }
      }
    } catch (e) {
      console.warn('Failed to load settings:', e)
    }
    return { ...DEFAULT_SETTINGS }
  }

  const settings = ref<AppSettings>(loadSettings())

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  const systemDark = ref(mediaQuery.matches)
  mediaQuery.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

  const isDark = computed(() => {
    if (settings.value.theme === 'dark') return true
    if (settings.value.theme === 'light') return false
    return systemDark.value
  })

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings.value))
    } catch (e) {
      console.error('Failed to save settings:', e)
    }
  }

  function resetToDefaults() {
    settings.value = { ...DEFAULT_SETTINGS }
    saveSettings()
  }

  function updateSetting<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    settings.value = {
      ...settings.value,
      [key]: value,
    }
    if (key === 'ttsLocale' && typeof value === 'string') {
      const defaultVoice = DEFAULT_LOCALE_EDGE_VOICES[value]
      if (defaultVoice) {
        settings.value.edgeVoice = defaultVoice
      }
    }
    saveSettings()
  }

  function getEffectiveTheme(): 'light' | 'dark' {
    return isDark.value ? 'dark' : 'light'
  }

  watch(
    isDark,
    (dark) => {
      const root = document.documentElement
      if (dark) {
        root.classList.add('dark')
      } else {
        root.classList.remove('dark')
      }
    },
    { immediate: true }
  )

  function getEffectiveModel(): string {
    const provider = settings.value.llmProvider
    if (provider === 'nim') return settings.value.nimModel || 'meta/llama-3.3-70b-instruct'
    if (provider === 'openrouter') return settings.value.openrouterModel || 'meta-llama/llama-3.3-70b-instruct'
    if (provider === 'gemini') return settings.value.geminiModel || 'gemini-2.5-flash'
    return settings.value.ollamaModel || settings.value.llmModel || 'qwen2.5:7b'
  }

  return {
    settings,
    isDark,
    saveSettings,
    resetToDefaults,
    updateSetting,
    getEffectiveTheme,
    getEffectiveModel,
  }
})