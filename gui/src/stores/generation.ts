import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const progress = ref(0)
  const bookFile = ref<File | null>(null)
  const bookTitle = ref('')
  const locale = ref('en_US')
  const ttsProvider = ref<'piper' | 'edge'>('piper')
  const llmProvider = ref<'ollama' | 'gemini' | 'openrouter'>('ollama')
  const llmModel = ref('qwen2.5:7b')
  const error = ref<string | null>(null)
  const outputPath = ref<string | null>(null)

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
    error.value = null
    outputPath.value = null
  }

  async function startGeneration() {
    if (isGenerating.value || !bookFile.value) return

    isGenerating.value = true
    progress.value = 0
    error.value = null
    outputPath.value = null

    try {
      // Convert File to base64 for transport to Rust
      const base64 = await fileToBase64(bookFile.value)
      const fileName = bookFile.value.name

      const result = await invoke<string>('generate_audiobook', {
        fileBase64: base64,
        fileName,
        bookTitle: bookTitle.value,
        locale: locale.value,
        ttsProvider: ttsProvider.value,
        llmProvider: llmProvider.value,
        llmModel: llmModel.value,
      })

      outputPath.value = result
      progress.value = 100
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      isGenerating.value = false
    }
  }

  function fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  function reset() {
    isGenerating.value = false
    progress.value = 0
    bookFile.value = null
    bookTitle.value = ''
    error.value = null
    outputPath.value = null
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
    error,
    outputPath,
    setBookFile,
    startGeneration,
    reset,
  }
})