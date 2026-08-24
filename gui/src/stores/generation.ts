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

  let progressInterval: number | null = null

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
    if (progressInterval) {
      clearInterval(progressInterval)
      progressInterval = null
    }
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

      // Start generation (non-blocking)
      invoke<string>('generate_audiobook', {
        fileBase64: base64,
        fileName,
        bookTitle: bookTitle.value,
        locale: locale.value,
        ttsProvider: ttsProvider.value,
        llmProvider: llmProvider.value,
        llmModel: llmModel.value,
      }).then((result) => {
        outputPath.value = result
        progress.value = 100
        isGenerating.value = false
        stopProgressPolling()
      }).catch((e) => {
        error.value = e instanceof Error ? e.message : String(e)
        isGenerating.value = false
        stopProgressPolling()
        throw e
      })

      // Start polling for progress
      startProgressPolling()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      isGenerating.value = false
      throw e
    }
  }

  function startProgressPolling() {
    if (progressInterval) return
    progressInterval = window.setInterval(async () => {
      try {
        const prog = await invoke<number>('get_generation_progress')
        progress.value = prog
      } catch {
        // Ignore errors, keep polling
      }
    }, 1000)
  }

  function stopProgressPolling() {
    if (progressInterval) {
      clearInterval(progressInterval)
      progressInterval = null
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
    stopProgressPolling()
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