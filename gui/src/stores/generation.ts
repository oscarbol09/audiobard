import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export type LLMProvider = 'ollama' | 'gemini' | 'openrouter'
export type TTSProvider = 'piper' | 'edge'

interface GenerationResult {
  session_id: string
  output_path: string
}

interface GenerationProgress {
  stage: string
  percent: number
  message: string
}

interface GenerateAudiobookArgs {
  fileBase64: string
  fileName: string
  bookTitle: string
  locale: string
  ttsProvider: TTSProvider
  llmProvider: LLMProvider
  llmModel: string
  sessionId: string
}

function toInvokeArgs(args: GenerateAudiobookArgs): Record<string, unknown> {
  return { ...args }
}

const PROGRESS_POLL_INTERVAL_MS = 1000

function generateSessionId(): string {
  // crypto.randomUUID is available in the Tauri webview (Chromium).
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '')
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const progress = ref(0)
  const stage = ref('idle')
  const message = ref('')
  const bookFile = ref<File | null>(null)
  const bookTitle = ref('')
  const locale = ref('en_US')
  const ttsProvider = ref<TTSProvider>('piper')
  const llmProvider = ref<LLMProvider>('ollama')
  const llmModel = ref('qwen2.5:7b')
  const error = ref<string | null>(null)
  const outputPath = ref<string | null>(null)
  const sessionId = ref<string | null>(null)

  let progressInterval: number | null = null

  function setBookFile(file: File | null): void {
    bookFile.value = file
    if (file) {
      bookTitle.value = file.name.replace(/\.[^/.]+$/, '')
    }
  }

  function reset(): void {
    stopProgressPolling()
    isGenerating.value = false
    progress.value = 0
    stage.value = 'idle'
    message.value = ''
    bookFile.value = null
    bookTitle.value = ''
    error.value = null
    outputPath.value = null
    sessionId.value = null
  }

  function stopProgressPolling(): void {
    if (progressInterval !== null) {
      clearInterval(progressInterval)
      progressInterval = null
    }
  }

  function startProgressPolling(): void {
    if (progressInterval !== null) return
    progressInterval = window.setInterval(() => {
      void pollOnce()
    }, PROGRESS_POLL_INTERVAL_MS)
  }

  async function pollOnce(): Promise<void> {
    const currentSession = sessionId.value
    if (currentSession === null) return
    try {
      const update = await invoke<GenerationProgress>('get_generation_progress', {
        sessionId: currentSession,
      })
      stage.value = update.stage
      progress.value = update.percent
      message.value = update.message
      if (update.stage === 'complete' || update.stage === 'error') {
        stopProgressPolling()
      }
    } catch {
      // Transient errors should not stop the poll; the next tick will retry.
    }
  }

  async function fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result
        if (typeof result !== 'string') {
          reject(new Error('Unexpected FileReader result'))
          return
        }
        resolve(result)
      }
      reader.onerror = () => reject(reader.error ?? new Error('FileReader failed'))
      reader.readAsDataURL(file)
    })
  }

  async function startGeneration(): Promise<void> {
    if (isGenerating.value) return
    if (bookFile.value === null) {
      throw new Error('No book file selected')
    }

    const sid = generateSessionId()
    sessionId.value = sid
    isGenerating.value = true
    progress.value = 0
    stage.value = 'queued'
    message.value = 'Starting'
    error.value = null
    outputPath.value = null

    const fileName = bookFile.value.name
    const base64 = await fileToBase64(bookFile.value)

    const args: GenerateAudiobookArgs = {
      fileBase64: base64,
      fileName,
      bookTitle: bookTitle.value,
      locale: locale.value,
      ttsProvider: ttsProvider.value,
      llmProvider: llmProvider.value,
      llmModel: llmModel.value,
      sessionId: sid,
    }

    startProgressPolling()

    try {
      const result = await invoke<string>('generate_audiobook', toInvokeArgs(args))
      const parsed = JSON.parse(result) as GenerationResult
      outputPath.value = parsed.output_path
      // The Rust side returns the session_id echoed back; keep ours as
      // the source of truth so a server-generated id would not surprise
      // a poll already in flight.
      sessionId.value = parsed.session_id || sid
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e))
      error.value = err.message
      stage.value = 'error'
      throw err
    } finally {
      isGenerating.value = false
    }
  }

  return {
    isGenerating,
    progress,
    stage,
    message,
    bookFile,
    bookTitle,
    locale,
    ttsProvider,
    llmProvider,
    llmModel,
    error,
    outputPath,
    sessionId,
    setBookFile,
    startGeneration,
    reset,
  }
})
