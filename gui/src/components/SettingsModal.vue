<script setup lang="ts">
import { computed, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useSettingsStore } from '../stores/settings'
import { useI18nStore } from '../stores/i18n'
import {
  NIM_MODELS,
  OPENROUTER_MODELS,
  GEMINI_MODELS,
  OLLAMA_MODELS,
  getModelInfo,
} from '../data/models'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const settingsStore = useSettingsStore()
const i18n = useI18nStore()
const { t } = i18n

const modelFilter = ref<'all' | 'free' | 'premium'>('all')

const filteredNimModels = computed(() => {
  if (modelFilter.value === 'free') return NIM_MODELS.filter((m) => m.freeTier)
  if (modelFilter.value === 'premium') return NIM_MODELS.filter((m) => !m.freeTier)
  return NIM_MODELS
})

const filteredOpenrouterModels = computed(() => {
  if (modelFilter.value === 'free') return OPENROUTER_MODELS.filter((m) => m.freeTier)
  if (modelFilter.value === 'premium') return OPENROUTER_MODELS.filter((m) => !m.freeTier)
  return OPENROUTER_MODELS
})

const filteredGeminiModels = computed(() => {
  if (modelFilter.value === 'free') return GEMINI_MODELS.filter((m) => m.freeTier)
  if (modelFilter.value === 'premium') return GEMINI_MODELS.filter((m) => !m.freeTier)
  return GEMINI_MODELS
})

const filteredOllamaModels = computed(() => {
  if (modelFilter.value === 'free') return OLLAMA_MODELS.filter((m) => m.freeTier)
  if (modelFilter.value === 'premium') return OLLAMA_MODELS.filter((m) => !m.freeTier)
  return OLLAMA_MODELS
})

function closeModal() {
  emit('update:modelValue', false)
}

function handleOverlayClick(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    closeModal()
  }
}

const themes = [
  { value: 'light', labelKey: 'themeLight' },
  { value: 'dark', labelKey: 'themeDark' },
  { value: 'system', labelKey: 'themeSystem' },
] as const

const selectedNimModelInfo = computed(() => getModelInfo('nim', settingsStore.settings.nimModel))
const selectedOpenrouterModelInfo = computed(() => getModelInfo('openrouter', settingsStore.settings.openrouterModel))
const selectedGeminiModelInfo = computed(() => getModelInfo('gemini', settingsStore.settings.geminiModel))
const selectedOllamaModelInfo = computed(() => getModelInfo('ollama', settingsStore.settings.ollamaModel))

async function selectOutputFolder() {
  try {
    const path = await invoke<string>('select_output_folder')
    if (path) {
      settingsStore.updateSetting('outputFolder', path)
    }
  } catch (e) {
    console.error('Failed to select output folder:', e)
  }
}

async function clearCache() {
  if (!confirm('This will delete all cached audio and LLM responses. Continue?')) return
  try {
    await invoke('clear_cache')
    alert(t('cacheCleared'))
  } catch (e) {
    console.error('Failed to clear cache:', e)
    alert('Failed to clear cache')
  }
}
</script>

<template>
  <Transition name="modal-fade">
    <div
      v-if="props.modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      @click="handleOverlayClick"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div
        class="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl bg-gray-900 border border-gray-700 shadow-xl"
      >
        <!-- Header -->
        <header class="flex items-center justify-between gap-4 p-6 border-b border-gray-800">
          <h2 id="settings-title" class="text-xl font-semibold text-gray-100">{{ t('settingsTitle') }}</h2>
          <button
            @click="closeModal"
            class="p-2 rounded-lg text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
            aria-label="Close settings"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <!-- Content -->
        <div class="p-6 space-y-8">
          <!-- Language Selection -->
          <section class="space-y-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
              </svg>
              {{ t('language') }}
            </h3>

            <div class="grid grid-cols-2 gap-4">
              <button
                type="button"
                @click="i18n.setLanguage('es')"
                :class="[
                  'p-3 rounded-lg border-2 transition-colors flex items-center justify-center gap-2 font-medium cursor-pointer',
                  settingsStore.settings.language === 'es'
                    ? 'border-brand-500 bg-brand-500/10 text-brand-400 font-bold'
                    : 'border-gray-700 hover:border-gray-600 text-gray-300'
                ]"
              >
                🇪🇸 {{ t('spanish') }}
              </button>
              <button
                type="button"
                @click="i18n.setLanguage('en')"
                :class="[
                  'p-3 rounded-lg border-2 transition-colors flex items-center justify-center gap-2 font-medium cursor-pointer',
                  settingsStore.settings.language === 'en'
                    ? 'border-brand-500 bg-brand-500/10 text-brand-400 font-bold'
                    : 'border-gray-700 hover:border-gray-600 text-gray-300'
                ]"
              >
                🇺🇸 {{ t('english') }}
              </button>
            </div>
          </section>

          <!-- LLM Settings & BYOK -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.48-.372c-.293-.226-.633-.456-1.01-.682l-1.964-.707v-.018c-.843-.33-1.706-.585-2.577-.733A6.043 6.043 0 006 13.298v2.552c0 .858.234 1.663.636 2.386l1.964.707c.377.226.717.456 1.09.682l.48.372c.632.632 1.432 1.09 2.293 1.386v.018c.843.33 1.706.585 2.577.733A6.043 6.043 0 0118 13.298v-2.552c0-.858-.234-1.663-.636-2.386l-1.964-.707c-.377-.226-.717-.456-1.09-.682l-.48-.372c-.632-.632-1.432-1.09-2.293-1.386v-.018z" />
              </svg>
              {{ t('llmSection') }}
            </h3>

            <div class="space-y-4">
              <!-- Provider Selection -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('llmProviderLabel') }}</label>
                <select
                  v-model="settingsStore.settings.llmProvider"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="ollama">{{ t('providerOllama') }}</option>
                  <option value="nim">{{ t('providerNim') }}</option>
                  <option value="openrouter">{{ t('providerOpenRouter') }}</option>
                  <option value="gemini">{{ t('providerGemini') }}</option>
                </select>
              </div>

                <!-- Ollama Options -->
                <div v-if="settingsStore.settings.llmProvider === 'ollama'" class="space-y-4 p-4 rounded-xl bg-gray-800/50 border border-gray-700/50">
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('ollamaHostLabel') }}</label>
                    <input
                      type="text"
                      v-model="settingsStore.settings.ollamaUrl"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      placeholder="http://localhost:11434"
                    />
                  </div>
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="text-sm font-medium text-gray-300">{{ t('ollamaModelLabel') }}</label>
                      <div class="inline-flex rounded-lg bg-gray-900/90 p-0.5 border border-gray-700 text-xs">
                        <button
                          type="button"
                          @click="modelFilter = 'all'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'all' ? 'bg-brand-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterAll') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'free'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'free' ? 'bg-green-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterFree') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'premium'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'premium' ? 'bg-purple-500 text-white font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterPremium') }}
                        </button>
                      </div>
                    </div>

                    <select
                      v-model="settingsStore.settings.ollamaModel"
                      @change="settingsStore.settings.llmModel = settingsStore.settings.ollamaModel"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-3 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    >
                      <option v-for="m in filteredOllamaModels" :key="m.value" :value="m.value">
                        {{ m.freeTier ? '⭐ [FREE]' : '💎 [PRO]' }} {{ m.label }}
                      </option>
                    </select>

                    <!-- Model Info Card -->
                    <div v-if="selectedOllamaModelInfo" class="p-3.5 rounded-lg bg-gray-900/80 border border-gray-700/80 space-y-2 mb-3">
                      <div class="flex items-center justify-between gap-2">
                        <span class="font-medium text-gray-200 text-sm">{{ selectedOllamaModelInfo.label }}</span>
                        <span class="text-xs px-2 py-0.5 rounded-full border" :class="selectedOllamaModelInfo.badgeClass">
                          {{ selectedOllamaModelInfo.badge }}
                        </span>
                      </div>
                      <p class="text-xs text-gray-300 leading-relaxed">{{ selectedOllamaModelInfo.description }}</p>
                      <div class="text-[11px] text-gray-500 font-mono flex items-center gap-2">
                        <span>{{ selectedOllamaModelInfo.specs }}</span>
                        <span>•</span>
                        <code>{{ selectedOllamaModelInfo.value }}</code>
                      </div>
                    </div>

                    <details class="text-xs text-gray-400">
                      <summary class="cursor-pointer hover:text-gray-300 mb-2">Ingresar modelo personalizado de Ollama...</summary>
                      <input
                        type="text"
                        v-model="settingsStore.settings.ollamaModel"
                        @input="settingsStore.settings.llmModel = settingsStore.settings.ollamaModel"
                        class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                        :placeholder="t('customModelPlaceholder')"
                      />
                    </details>
                  </div>
                </div>

                <!-- NVIDIA NIM Options (BYOK) -->
                <div v-if="settingsStore.settings.llmProvider === 'nim'" class="space-y-4 p-4 rounded-xl bg-green-950/20 border border-green-800/40">
                  <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center gap-2 text-green-400 font-semibold">
                      <span>⚡ NVIDIA NIM (build.nvidia.com)</span>
                    </div>
                    <span class="text-xs text-green-400/80 bg-green-900/30 px-2 py-0.5 rounded border border-green-700/30">
                      Free Tier API
                    </span>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">NVIDIA NIM {{ t('apiKeyLabel') }}</label>
                    <input
                      type="password"
                      v-model="settingsStore.settings.nimApiKey"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                      placeholder="nvapi-..."
                    />
                    <p class="text-xs text-gray-500 mt-1">Obtén tu API key gratuita en <a href="https://build.nvidia.com" target="_blank" class="text-green-400 underline">build.nvidia.com</a> (sin tarjeta requerida).</p>
                  </div>
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="text-sm font-medium text-gray-300">Catálogo de Modelos NVIDIA NIM</label>
                      <div class="inline-flex rounded-lg bg-gray-900/90 p-0.5 border border-gray-700 text-xs">
                        <button
                          type="button"
                          @click="modelFilter = 'all'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'all' ? 'bg-brand-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterAll') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'free'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'free' ? 'bg-green-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterFree') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'premium'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'premium' ? 'bg-purple-500 text-white font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterPremium') }}
                        </button>
                      </div>
                    </div>

                    <select
                      v-model="settingsStore.settings.nimModel"
                      @change="settingsStore.settings.llmModel = settingsStore.settings.nimModel"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-3 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                    >
                      <option v-for="m in filteredNimModels" :key="m.value" :value="m.value">
                        {{ m.freeTier ? '⭐ [FREE]' : '💎 [PRO]' }} {{ m.label }}
                      </option>
                    </select>

                    <!-- Model Info Card / Recommendation -->
                    <div v-if="selectedNimModelInfo" class="p-3.5 rounded-lg bg-gray-900/90 border border-green-800/50 space-y-2 mb-3">
                      <div class="flex items-center justify-between gap-2 flex-wrap">
                        <span class="font-semibold text-green-300 text-sm">{{ selectedNimModelInfo.label }}</span>
                        <span class="text-xs px-2.5 py-0.5 rounded-full border font-medium" :class="selectedNimModelInfo.badgeClass">
                          {{ selectedNimModelInfo.badge }}
                        </span>
                      </div>
                      <p class="text-xs text-gray-300 leading-relaxed">{{ selectedNimModelInfo.description }}</p>
                      <div class="text-[11px] text-gray-400 font-mono flex items-center justify-between pt-1 border-t border-gray-800">
                        <span>{{ selectedNimModelInfo.specs }}</span>
                        <code class="text-green-400">{{ selectedNimModelInfo.value }}</code>
                      </div>
                    </div>

                    <details class="text-xs text-gray-400">
                      <summary class="cursor-pointer hover:text-green-300 mb-2">Ingresar ID de modelo personalizado de NVIDIA NIM...</summary>
                      <input
                        type="text"
                        v-model="settingsStore.settings.nimModel"
                        @input="settingsStore.settings.llmModel = settingsStore.settings.nimModel"
                        class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        :placeholder="t('customModelPlaceholder')"
                      />
                    </details>
                  </div>
                </div>

                <!-- OpenRouter Options (BYOK) -->
                <div v-if="settingsStore.settings.llmProvider === 'openrouter'" class="space-y-4 p-4 rounded-xl bg-purple-950/20 border border-purple-800/40">
                  <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center gap-2 text-purple-400 font-semibold">
                      <span>🌐 OpenRouter Cloud</span>
                    </div>
                    <span class="text-xs text-purple-400/80 bg-purple-900/30 px-2 py-0.5 rounded border border-purple-700/30">
                      Modelos Free & BYOK
                    </span>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">OpenRouter {{ t('apiKeyLabel') }}</label>
                    <input
                      type="password"
                      v-model="settingsStore.settings.openrouterApiKey"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                      placeholder="sk-or-v1-..."
                    />
                  </div>
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="text-sm font-medium text-gray-300">Catálogo de Modelos OpenRouter</label>
                      <div class="inline-flex rounded-lg bg-gray-900/90 p-0.5 border border-gray-700 text-xs">
                        <button
                          type="button"
                          @click="modelFilter = 'all'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'all' ? 'bg-brand-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterAll') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'free'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'free' ? 'bg-green-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterFree') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'premium'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'premium' ? 'bg-purple-500 text-white font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterPremium') }}
                        </button>
                      </div>
                    </div>

                    <select
                      v-model="settingsStore.settings.openrouterModel"
                      @change="settingsStore.settings.llmModel = settingsStore.settings.openrouterModel"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-3 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    >
                      <option v-for="m in filteredOpenrouterModels" :key="m.value" :value="m.value">
                        {{ m.freeTier ? '⭐ [FREE]' : '💎 [PRO]' }} {{ m.label }}
                      </option>
                    </select>

                    <!-- Model Info Card -->
                    <div v-if="selectedOpenrouterModelInfo" class="p-3.5 rounded-lg bg-gray-900/90 border border-purple-800/50 space-y-2 mb-3">
                      <div class="flex items-center justify-between gap-2 flex-wrap">
                        <span class="font-semibold text-purple-300 text-sm">{{ selectedOpenrouterModelInfo.label }}</span>
                        <span class="text-xs px-2.5 py-0.5 rounded-full border font-medium" :class="selectedOpenrouterModelInfo.badgeClass">
                          {{ selectedOpenrouterModelInfo.badge }}
                        </span>
                      </div>
                      <p class="text-xs text-gray-300 leading-relaxed">{{ selectedOpenrouterModelInfo.description }}</p>
                      <div class="text-[11px] text-gray-400 font-mono flex items-center justify-between pt-1 border-t border-gray-800">
                        <span>{{ selectedOpenrouterModelInfo.specs }}</span>
                        <code class="text-purple-400">{{ selectedOpenrouterModelInfo.value }}</code>
                      </div>
                    </div>

                    <details class="text-xs text-gray-400">
                      <summary class="cursor-pointer hover:text-purple-300 mb-2">Ingresar ID de modelo personalizado de OpenRouter...</summary>
                      <input
                        type="text"
                        v-model="settingsStore.settings.openrouterModel"
                        @input="settingsStore.settings.llmModel = settingsStore.settings.openrouterModel"
                        class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                        :placeholder="t('customModelPlaceholder')"
                      />
                    </details>
                  </div>
                </div>

                <!-- Gemini Options (BYOK) -->
                <div v-if="settingsStore.settings.llmProvider === 'gemini'" class="space-y-4 p-4 rounded-xl bg-blue-950/20 border border-blue-800/40">
                  <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center gap-2 text-blue-400 font-semibold">
                      <span>✨ Google Gemini API</span>
                    </div>
                    <span class="text-xs text-blue-400/80 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-700/30">
                      Google AI Studio
                    </span>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">Gemini {{ t('apiKeyLabel') }}</label>
                    <input
                      type="password"
                      v-model="settingsStore.settings.geminiApiKey"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="AIzaSy..."
                    />
                  </div>
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="text-sm font-medium text-gray-300">Modelos Google Gemini</label>
                      <div class="inline-flex rounded-lg bg-gray-900/90 p-0.5 border border-gray-700 text-xs">
                        <button
                          type="button"
                          @click="modelFilter = 'all'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'all' ? 'bg-brand-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterAll') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'free'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'free' ? 'bg-green-500 text-gray-900 font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterFree') }}
                        </button>
                        <button
                          type="button"
                          @click="modelFilter = 'premium'"
                          class="px-2 py-0.5 rounded transition-colors"
                          :class="modelFilter === 'premium' ? 'bg-purple-500 text-white font-semibold shadow' : 'text-gray-400 hover:text-gray-200'"
                        >
                          {{ t('filterPremium') }}
                        </button>
                      </div>
                    </div>

                    <select
                      v-model="settingsStore.settings.geminiModel"
                      @change="settingsStore.settings.llmModel = settingsStore.settings.geminiModel"
                      class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option v-for="m in filteredGeminiModels" :key="m.value" :value="m.value">
                        {{ m.freeTier ? '⭐ [FREE]' : '💎 [PRO]' }} {{ m.label }}
                      </option>
                    </select>

                  <!-- Model Info Card -->
                  <div v-if="selectedGeminiModelInfo" class="p-3.5 rounded-lg bg-gray-900/90 border border-blue-800/50 space-y-2 mb-3">
                    <div class="flex items-center justify-between gap-2 flex-wrap">
                      <span class="font-semibold text-blue-300 text-sm">{{ selectedGeminiModelInfo.label }}</span>
                      <span class="text-xs px-2.5 py-0.5 rounded-full border font-medium" :class="selectedGeminiModelInfo.badgeClass">
                        {{ selectedGeminiModelInfo.badge }}
                      </span>
                    </div>
                    <p class="text-xs text-gray-300 leading-relaxed">{{ selectedGeminiModelInfo.description }}</p>
                    <div class="text-[11px] text-gray-400 font-mono flex items-center justify-between pt-1 border-t border-gray-800">
                      <span>{{ selectedGeminiModelInfo.specs }}</span>
                      <code class="text-blue-400">{{ selectedGeminiModelInfo.value }}</code>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- TTS Settings -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6m-6 0a3 3 0 116 0v6m0 0l3-3m-3 3l-3-3m6 0a3 3 0 10-6 0m0 0l3-3m3 3l-3 3" />
              </svg>
              {{ t('ttsSection') }}
            </h3>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('ttsProviderLabel') }}</label>
                <select
                  v-model="settingsStore.settings.ttsProvider"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="piper">Piper (Local, Free)</option>
                  <option value="edge">Edge TTS (Cloud, Free)</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('voiceLocaleLabel') }}</label>
                <select
                  v-model="settingsStore.settings.ttsLocale"
                  @change="settingsStore.updateSetting('ttsLocale', settingsStore.settings.ttsLocale)"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="es_MX">{{ t('localeEsMx') }}</option>
                  <option value="es_CO">{{ t('localeEsCo') }}</option>
                  <option value="es_ES">{{ t('localeEsEs') }}</option>
                  <option value="en_US">{{ t('localeEnUs') }}</option>
                  <option value="fr_FR">{{ t('localeFrFr') }}</option>
                  <option value="de_DE">{{ t('localeDeDe') }}</option>
                  <option value="it_IT">{{ t('localeItIt') }}</option>
                </select>
              </div>

              <div v-if="settingsStore.settings.ttsProvider === 'piper'" class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-300 mb-2">Piper Voice</label>
                <input
                  type="text"
                  v-model="settingsStore.settings.piperVoice"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="e.g., en_US-lessac-medium"
                />
              </div>

              <div v-if="settingsStore.settings.ttsProvider === 'edge'" class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-300 mb-2">Edge Voice</label>
                <input
                  type="text"
                  v-model="settingsStore.settings.edgeVoice"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="e.g., en-US-AriaNeural"
                />
              </div>
            </div>
          </section>

          <!-- Appearance -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M12 18h.01M12 12h.01" />
              </svg>
              {{ t('appearanceSection') }}
            </h3>

            <div class="grid grid-cols-3 gap-4">
              <button
                v-for="theme in themes"
                :key="theme.value"
                @click="settingsStore.updateSetting('theme', theme.value)"
                :class="[
                  'p-4 rounded-lg border-2 transition-colors flex flex-col items-center gap-2',
                  settingsStore.settings.theme === theme.value
                    ? 'border-brand-500 bg-brand-500/10'
                    : 'border-gray-700 hover:border-gray-600'
                ]"
              >
                <span class="text-lg font-medium text-gray-100 capitalize">{{ t(theme.labelKey) }}</span>
              </button>
            </div>
          </section>

          <!-- Cache & Output -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              {{ t('cacheSection') }}
            </h3>

            <div class="flex items-center gap-4">
              <button
                @click="clearCache"
                class="px-4 py-2 text-sm font-medium text-red-400 bg-red-950/30 border border-red-800/40 rounded-lg hover:bg-red-900/40 transition-colors"
              >
                {{ t('clearCacheBtn') }}
              </button>
            </div>

            <div class="pt-2">
              <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('outputFolderLabel') }}</label>
              <div class="flex gap-2">
                <input
                  type="text"
                  v-model="settingsStore.settings.outputFolder"
                  placeholder="Default: ~/AudioBard/output"
                  class="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                />
                <button
                  @click="selectOutputFolder"
                  class="px-4 py-2 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors"
                >
                  {{ t('browseBtn') }}
                </button>
              </div>
            </div>
          </section>
        </div>

        <!-- Footer -->
        <footer class="flex items-center justify-end gap-3 p-6 border-t border-gray-800">
          <button
            @click="settingsStore.resetToDefaults"
            class="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-600 hover:text-gray-100 transition-colors"
          >
            {{ t('resetDefaults') }}
          </button>
          <button
            @click="closeModal"
            class="px-4 py-2 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors"
          >
            {{ t('closeBtn') }}
          </button>
        </footer>
      </div>
    </div>
  </Transition>
</template>