<script setup lang="ts">
import { invoke } from '@tauri-apps/api/core'
import { useSettingsStore } from '../stores/settings'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const settingsStore = useSettingsStore()

function closeModal() {
  emit('update:modelValue', false)
}

function handleOverlayClick(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    closeModal()
  }
}

const themes = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
] as const

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
    alert('Cache cleared successfully')
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
          <h2 id="settings-title" class="text-xl font-semibold text-gray-100">Settings</h2>
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
          <!-- LLM Settings -->
          <section class="space-y-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.48-.372c-.293-.226-.633-.456-1.01-.682l-1.964-.707v-.018c-.843-.33-1.706-.585-2.577-.733A6.043 6.043 0 006 13.298v2.552c0 .858.234 1.663.636 2.386l1.964.707c.377.226.717.456 1.09.682l.48.372c.632.632 1.432 1.09 2.293 1.386v.018c.843.33 1.706.585 2.577.733A6.043 6.043 0 0118 13.298v-2.552c0-.858-.234-1.663-.636-2.386l-1.964-.707c-.377-.226-.717-.456-1.09-.682l-.48-.372c-.632-.632-1.432-1.09-2.293-1.386v-.018z" />
              </svg>
              LLM Settings
            </h3>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- LLM Provider -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">LLM Provider</label>
                <select
                  v-model="settingsStore.settings.llmProvider"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="gemini">Gemini (Cloud)</option>
                  <option value="openrouter">OpenRouter (Cloud)</option>
                </select>
              </div>

              <!-- LLM Model -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">LLM Model</label>
                <input
                  type="text"
                  v-model="settingsStore.settings.llmModel"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="e.g., qwen2.5:7b"
                />
              </div>

              <!-- Ollama URL -->
              <div v-if="settingsStore.settings.llmProvider === 'ollama'" class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-300 mb-2">Ollama URL</label>
                <input
                  type="text"
                  v-model="settingsStore.settings.ollamaUrl"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="http://localhost:11434"
                />
              </div>

              <!-- Gemini API Key -->
              <div v-if="settingsStore.settings.llmProvider === 'gemini'" class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-300 mb-2">Gemini API Key</label>
                <input
                  type="password"
                  v-model="settingsStore.settings.geminiApiKey"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="Enter your Gemini API key"
                />
              </div>

              <!-- OpenRouter API Key -->
              <div v-if="settingsStore.settings.llmProvider === 'openrouter'" class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-300 mb-2">OpenRouter API Key</label>
                <input
                  type="password"
                  v-model="settingsStore.settings.openrouterApiKey"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="Enter your OpenRouter API key"
                />
              </div>
            </div>
          </section>

          <!-- TTS Settings -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6m-6 0a3 3 0 116 0v6m0 0l3-3m-3 3l-3-3m6 0a3 3 0 10-6 0m0 0l3-3m3 3l-3 3" />
              </svg>
              TTS Settings
            </h3>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">TTS Provider</label>
                <select
                  v-model="settingsStore.settings.ttsProvider"
                  class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="piper">Piper (Local, Free)</option>
                  <option value="edge">Edge TTS (Cloud, Free)</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">Locale</label>
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
              Appearance
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
                <span class="text-lg font-medium text-gray-100 capitalize">{{ theme.label }}</span>
                <span class="text-xs text-gray-500">
                  {{ theme.value === 'system' ? 'Follows OS' : theme.value === 'dark' ? 'Dark mode' : 'Light mode' }}
                </span>
              </button>
            </div>
          </section>

          <!-- Cache -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              Cache Management
            </h3>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">Max Cache Size</label>
                <div class="flex items-center gap-2">
                  <input
                    type="number"
                    v-model.number="settingsStore.settings.maxCacheSizeGB"
                    min="1"
                    max="100"
                    class="w-24 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  />
                  <span class="text-gray-500">GB</span>
                </div>
              </div>

              <div class="flex items-end">
                <button
                  @click="clearCache"
                  class="px-4 py-2 text-sm font-medium text-gray-900 bg-red-500 hover:bg-red-400 rounded-lg transition-colors"
                >
                  Clear Cache
                </button>
              </div>
            </div>
          </section>

          <!-- Output Folder -->
          <section class="space-y-4 border-t border-gray-800 pt-4">
            <h3 class="text-lg font-semibold text-gray-100 flex items-center gap-2">
              <svg class="w-5 h-5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h14" />
              </svg>
              Output Folder
            </h3>

            <div class="flex items-center gap-3">
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
                Browse...
              </button>
            </div>
            <p class="text-xs text-gray-500">Leave empty to use default location (~/AudioBard/output)</p>
          </section>
        </div>

        <!-- Footer -->
        <footer class="flex items-center justify-end gap-3 pt-6 border-t border-gray-800">
          <button
            @click="settingsStore.resetToDefaults"
            class="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-600 hover:text-gray-100 transition-colors"
          >
            Reset to Defaults
          </button>
          <button
            @click="closeModal"
            class="px-4 py-2 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors"
          >
            Close
          </button>
        </footer>
      </div>
    </Transition>
  </div>
</template>