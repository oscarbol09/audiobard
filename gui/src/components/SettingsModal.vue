<script setup lang="ts">
import { invoke } from '@tauri-apps/api/core'
import { useSettingsStore } from '../stores/settings'
import { useI18nStore } from '../stores/i18n'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const settingsStore = useSettingsStore()
const i18n = useI18nStore()
const { t } = i18n

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

const nimModels = [
  { value: 'meta/llama-3.3-70b-instruct', label: 'Meta Llama 3.3 70B Instruct' },
  { value: 'nvidia/llama-3.1-nemotron-70b-instruct', label: 'NVIDIA Llama 3.1 Nemotron 70B' },
  { value: 'deepseek-ai/deepseek-r1', label: 'DeepSeek R1' },
  { value: 'mistralai/mistral-large-2-instruct', label: 'Mistral Large 2' },
]

const openrouterModels = [
  { value: 'deepseek/deepseek-chat-v3-0324:free', label: 'DeepSeek V3 (Free)' },
  { value: 'meta-llama/llama-3.3-70b-instruct', label: 'Meta Llama 3.3 70B' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
]

const geminiModels = [
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Reasoning)' },
]

const ollamaModels = [
  { value: 'qwen2.5:7b', label: 'Qwen 2.5 7B (Recommended)' },
  { value: 'llama3.1:8b', label: 'Llama 3.1 8B' },
  { value: 'gemma2:9b', label: 'Gemma 2 9B' },
]

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
                  <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('ollamaModelLabel') }}</label>
                  <select
                    v-model="settingsStore.settings.llmModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-2 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  >
                    <option v-for="m in ollamaModels" :key="m.value" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input
                    type="text"
                    v-model="settingsStore.settings.llmModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    :placeholder="t('customModelPlaceholder')"
                  />
                </div>
              </div>

              <!-- NVIDIA NIM Options (BYOK) -->
              <div v-if="settingsStore.settings.llmProvider === 'nim'" class="space-y-4 p-4 rounded-xl bg-green-950/20 border border-green-800/40">
                <div class="flex items-center gap-2 text-green-400 text-sm font-semibold">
                  <span>⚡ NVIDIA NIM (build.nvidia.com)</span>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-300 mb-2">NVIDIA NIM {{ t('apiKeyLabel') }}</label>
                  <input
                    type="password"
                    v-model="settingsStore.settings.nimApiKey"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                    placeholder="nvapi-..."
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('modelPresetLabel') }}</label>
                  <select
                    v-model="settingsStore.settings.nimModel"
                    @change="settingsStore.settings.llmModel = settingsStore.settings.nimModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-2 focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  >
                    <option v-for="m in nimModels" :key="m.value" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input
                    type="text"
                    v-model="settingsStore.settings.nimModel"
                    @input="settingsStore.settings.llmModel = settingsStore.settings.nimModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500"
                    :placeholder="t('customModelPlaceholder')"
                  />
                </div>
              </div>

              <!-- OpenRouter Options (BYOK) -->
              <div v-if="settingsStore.settings.llmProvider === 'openrouter'" class="space-y-4 p-4 rounded-xl bg-purple-950/20 border border-purple-800/40">
                <div class="flex items-center gap-2 text-purple-400 text-sm font-semibold">
                  <span>🌐 OpenRouter Cloud</span>
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
                  <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('modelPresetLabel') }}</label>
                  <select
                    v-model="settingsStore.settings.llmModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    <option v-for="m in openrouterModels" :key="m.value" :value="m.value">{{ m.label }}</option>
                  </select>
                  <input
                    type="text"
                    v-model="settingsStore.settings.llmModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    :placeholder="t('customModelPlaceholder')"
                  />
                </div>
              </div>

              <!-- Gemini Options (BYOK) -->
              <div v-if="settingsStore.settings.llmProvider === 'gemini'" class="space-y-4 p-4 rounded-xl bg-blue-950/20 border border-blue-800/40">
                <div class="flex items-center gap-2 text-blue-400 text-sm font-semibold">
                  <span>✨ Google Gemini API</span>
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
                  <label class="block text-sm font-medium text-gray-300 mb-2">{{ t('modelPresetLabel') }}</label>
                  <select
                    v-model="settingsStore.settings.llmModel"
                    class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 mb-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option v-for="m in geminiModels" :key="m.value" :value="m.value">{{ m.label }}</option>
                  </select>
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
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="en_US">English (US)</option>
                  <option value="es_ES">Spanish (Spain)</option>
                  <option value="fr_FR">French (France)</option>
                  <option value="de_DE">German (Germany)</option>
                  <option value="it_IT">Italian (Italy)</option>
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