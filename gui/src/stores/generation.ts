import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const progress = ref(0)
  const bookFile = ref<File | null>(null)
  const bookTitle = ref('')
  const locale = ref('en_US')
  const ttsProvider = ref<'piper' | 'edge'>('piper')
  const llmProvider = ref<'ollama' | 'gemini' | 'openrouter'>('ollama')
  const llmModel = ref('qwen2.5:7b')

  function setBookFile(file: File | null) {
    bookFile.value = file
    if (file) {
      bookTitle.value = file.name.replace(/\.[^/.]+$/, '')
    }
  }

  function reset() {
    isGenerating.value = false
    progress.value = 0
    bookFile.value = null
    bookTitle.value = ''
  }

  return {
    isGenerating,
    progress,
    bookFile,
    bookTitle,
    locale,
    ttsProvider,
    llmProvider,
    llmModel,
    setBookFile,
    reset,
  }
})