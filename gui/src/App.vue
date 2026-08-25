<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useGenerationStore } from './stores/generation'
import { useSettingsStore } from './stores/settings'
import { useI18nStore } from './stores/i18n'
import {
  NIM_MODELS,
  OPENROUTER_MODELS,
  GEMINI_MODELS,
  OLLAMA_MODELS,
  getModelInfo,
} from './data/models'
import UploadSection from './components/UploadSection.vue'
import GenerationProgress from './components/GenerationProgress.vue'
import LibraryPanel from './components/LibraryPanel.vue'
import SettingsModal from './components/SettingsModal.vue'

const showSettings = ref(false)

const healthOk = ref(false)
const healthError = ref<string | null>(null)
const checking = ref(true)

const generationStore = useGenerationStore()
const settingsStore = useSettingsStore()
const i18n = useI18nStore()
const { t } = i18n

const availableModels = computed(() => {
  const provider = settingsStore.settings.llmProvider
  if (provider === 'nim') return NIM_MODELS
  if (provider === 'openrouter') return OPENROUTER_MODELS
  if (provider === 'gemini') return GEMINI_MODELS
  return OLLAMA_MODELS
})

const activeModelInfo = computed(() => {
  const provider = settingsStore.settings.llmProvider
  const currentModel = settingsStore.getEffectiveModel()
  return getModelInfo(provider, currentModel)
})

function updateActiveModel(val: string) {
  const provider = settingsStore.settings.llmProvider
  if (provider === 'nim') {
    settingsStore.updateSetting('nimModel', val)
  } else if (provider === 'openrouter') {
    settingsStore.updateSetting('openrouterModel', val)
  } else if (provider === 'gemini') {
    settingsStore.updateSetting('geminiModel', val)
  } else {
    settingsStore.updateSetting('ollamaModel', val)
    settingsStore.updateSetting('llmModel', val)
  }
}

async function checkHealth() {
  checking.value = true
  healthError.value = null
  try {
    const ok = await invoke<boolean>('check_server_health')
    healthOk.value = ok
    if (!ok) {
      healthError.value = 'FastAPI server health check failed'
    }
  } catch (e) {
    healthError.value = e instanceof Error ? e.message : String(e)
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  setInterval(async () => {
    if (!healthOk.value) {
      await checkHealth()
    }
  }, 2000)

  checkHealth()
})

function handleFileError(message: string) {
  console.error('File error:', message)
}

async function onGenerate(): Promise<void> {
  try {
    await generationStore.startGeneration()
  } catch (err) {
    console.error('Generation failed:', err)
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
    <!-- Health Check Blocking Screen -->
    <div v-if="!healthOk" class="flex-1 flex flex-col items-center justify-center p-6">
      <div class="text-center space-y-6 max-w-md">
        <div class="inline-flex items-center justify-center">
          <svg class="animate-spin h-16 w-16 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <div class="space-y-2">
          <h1 class="text-3xl font-extrabold tracking-tight text-brand-500">AudioBard</h1>
          <p class="text-gray-400" v-if="checking">Starting FastAPI server...</p>
          <p class="text-gray-400" v-else-if="healthError">Health check failed: {{ healthError }}</p>
          <p class="text-gray-400" v-else>Waiting for server...</p>
        </div>
        <div v-if="healthError" class="text-sm text-red-400">
          Retrying in 2 seconds...
        </div>
      </div>
    </div>

    <!-- Main App Content -->
    <div v-else class="flex-1 flex flex-col">
      <header class="border-b border-gray-800 px-6 py-4">
        <div class="max-w-4xl mx-auto flex items-center justify-between">
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-extrabold tracking-tight text-brand-500">AudioBard</h1>
            <span class="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
              {{ t('subtitle') }}
            </span>
          </div>
          <div class="flex items-center gap-4">
            <span class="px-3 py-1 text-xs font-medium text-green-400 bg-green-900/30 rounded-full">
              Server Ready
            </span>
            <button
              @click="showSettings = true"
              aria-label="Open settings"
              class="p-2 rounded-lg text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors flex items-center gap-2"
            >
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span class="text-sm font-medium hidden sm:inline">{{ t('settings') }}</span>
            </button>
          </div>
        </div>
      </header>

      <main class="flex-1 p-6">
        <div class="max-w-4xl mx-auto space-y-8">
          <!-- Upload Section -->
          <section>
            <UploadSection
              v-model="generationStore.bookFile"
              :accepted-types="['txt', 'epub']"
              :maxSizeMB="50"
              @error="handleFileError"
            />
          </section>

          <!-- Book Details & Generation Options -->
          <section v-if="generationStore.bookFile" class="space-y-6 border-t border-gray-800 pt-8">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <!-- Locale -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('voiceLocaleLabel') }}</label>
                <select
                  :value="settingsStore.settings.ttsLocale"
                  @change="e => settingsStore.updateSetting('ttsLocale', (e.target as HTMLSelectElement).value)"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="en_US">English (US)</option>
                  <option value="es_ES">Spanish (Spain)</option>
                  <option value="fr_FR">French (France)</option>
                  <option value="de_DE">German (Germany)</option>
                  <option value="it_IT">Italian (Italy)</option>
                </select>
              </div>

              <!-- TTS Provider -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('ttsProviderLabel') }}</label>
                <select
                  :value="settingsStore.settings.ttsProvider"
                  @change="e => settingsStore.updateSetting('ttsProvider', (e.target as HTMLSelectElement).value as any)"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="piper">Piper (Local, Free)</option>
                  <option value="edge">Edge TTS (Cloud, Free)</option>
                </select>
              </div>

              <!-- LLM Provider -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('llmProviderLabel') }}</label>
                <select
                  :value="settingsStore.settings.llmProvider"
                  @change="e => settingsStore.updateSetting('llmProvider', (e.target as HTMLSelectElement).value as any)"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="ollama">{{ t('providerOllama') }}</option>
                  <option value="nim">{{ t('providerNim') }}</option>
                  <option value="openrouter">{{ t('providerOpenRouter') }}</option>
                  <option value="gemini">{{ t('providerGemini') }}</option>
                </select>
              </div>

              <!-- LLM Model -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('modelPresetLabel') }}</label>
                <select
                  :value="settingsStore.getEffectiveModel()"
                  @change="e => updateActiveModel((e.target as HTMLSelectElement).value)"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option v-for="m in availableModels" :key="m.value" :value="m.value">
                    {{ m.badge.split(' ')[0] }} {{ m.label }}
                  </option>
                </select>

                <!-- Model Info & Recommendation -->
                <div v-if="activeModelInfo" class="mt-2 text-xs flex items-center justify-between text-gray-400 bg-gray-900/80 p-2.5 rounded-lg border border-gray-800 gap-2">
                  <span class="truncate text-gray-300">{{ activeModelInfo.description }}</span>
                  <span class="flex-shrink-0 px-2 py-0.5 rounded border text-[11px]" :class="activeModelInfo.badgeClass">
                    {{ activeModelInfo.badge }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Generate Button -->
            <div class="pt-4 border-t border-gray-800">
              <button
                class="w-full px-6 py-3 text-lg font-semibold text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="generationStore.isGenerating"
                @click="onGenerate"
              >
                <span v-if="!generationStore.isGenerating">{{ t('generateBtn') }}</span>
                <span v-else class="flex items-center justify-center gap-2">
                  <svg class="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {{ t('progressTitle') }}
                </span>
              </button>
            </div>

            <GenerationProgress />
          </section>

          <!-- Library Panel -->
          <LibraryPanel />
        </div>
      </main>
    </div>

    <!-- Settings Modal -->
    <SettingsModal v-model="showSettings" />
  </div>
</template>