import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const llmProvider = ref('ollama')
  const ttsProvider = ref('piper')
  return { llmProvider, ttsProvider }
})
