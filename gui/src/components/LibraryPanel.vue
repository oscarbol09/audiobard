<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useI18nStore } from '../stores/i18n'
import { useGenerationStore } from '../stores/generation'

interface LibraryBook {
  id: number
  title: string
  path: string
  total_paragraphs: number
  total_words: number
  dialog_ratio: number
  created_at: string | null
  has_audio?: boolean
}

const books = ref<LibraryBook[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const searchQuery = ref('')
const showIncomplete = ref(false)

const i18n = useI18nStore()
const { t } = i18n
const generationStore = useGenerationStore()

watch(() => generationStore.stage, (newStage) => {
  if (newStage === 'complete') {
    loadLibrary()
  }
})

async function loadLibrary() {
  loading.value = true
  error.value = null
  try {
    const result = await invoke<LibraryBook[]>('get_library')
    books.value = result
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    console.error('Failed to load library:', e)
  } finally {
    loading.value = false
  }
}

const filteredBooks = computed(() => {
  let list = books.value
  if (!showIncomplete.value) {
    list = list.filter((b) => b.has_audio !== false)
  }
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter((b) => b.title.toLowerCase().includes(q))
})

const hasAnyIncomplete = computed(() => {
  return books.value.some((b) => b.has_audio === false)
})

async function onDownload(book: LibraryBook) {
  try {
    const path = await invoke<string>('download_book', { bookId: book.id, book_id: book.id })
    await invoke('shell.open', { path })
  } catch (e) {
    console.error('Download/Open failed:', e)
  }
}

async function onRegenerate(book: LibraryBook) {
  if (!confirm(`Regenerate "${book.title}"? This will overwrite the existing audio.`)) return
  try {
    await invoke('regenerate_book', { bookId: book.id, book_id: book.id, settings: {} })
    alert('Regeneration started! Check the generation progress.')
  } catch (e) {
    console.error('Regenerate failed:', e)
    alert(`Regenerate failed: ${e instanceof Error ? e.message : String(e)}`)
  }
}

async function onDelete(book: LibraryBook) {
  if (!confirm(t('deleteConfirm'))) return
  try {
    await invoke('delete_book', { bookId: book.id, book_id: book.id })
    books.value = books.value.filter((b) => b.id !== book.id)
    await loadLibrary()
  } catch (e) {
    console.error('Delete failed:', e)
    alert(`Error: ${e instanceof Error ? e.message : String(e)}`)
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  // Normalize SQLite UTC timestamp format "YYYY-MM-DD HH:MM:SS" to ISO-8601 UTC
  let s = iso.trim()
  if (!s.endsWith('Z') && !s.includes('+') && !s.includes('T')) {
    s = s.replace(' ', 'T') + 'Z'
  } else if (!s.endsWith('Z') && !s.includes('+')) {
    s = s + 'Z'
  }
  const d = new Date(s)
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadLibrary()
})
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <h2 class="text-xl font-bold tracking-tight text-gray-100">{{ t('libraryTitle') }}</h2>
      <div class="flex items-center gap-3 flex-wrap">
        <!-- Incomplete filter toggle -->
        <label v-if="hasAnyIncomplete" class="text-xs text-gray-400 flex items-center gap-1.5 cursor-pointer hover:text-gray-200">
          <input
            type="checkbox"
            v-model="showIncomplete"
            class="rounded bg-gray-900 border-gray-700 text-brand-500 focus:ring-brand-500 h-3.5 w-3.5"
          />
          <span>{{ t('showAllToggle') }}</span>
        </label>

        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('searchPlaceholder')"
          class="px-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-shadow w-44 sm:w-48"
        />
        <button
          @click="loadLibrary"
          :disabled="loading"
          class="px-3 py-1.5 text-sm font-medium text-brand-400 bg-brand-500/10 hover:bg-brand-500/20 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <svg
            class="w-4 h-4"
            :class="{ 'animate-spin': loading }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{{ t('refreshBtn') }}</span>
        </button>
      </div>
    </div>

    <div v-if="loading && books.length === 0" class="text-center py-8 text-gray-400">{{ t('loadingLibrary') }}</div>
    <div v-else-if="error" class="text-center py-8 text-red-400">{{ error }}</div>
    <div v-else-if="filteredBooks.length === 0" class="text-center py-12 border-2 border-dashed border-gray-800 rounded-xl">
      <p class="text-gray-400">{{ searchQuery ? t('noSearchMatch') : t('noBooks') }}</p>
    </div>
    
    <ul v-else class="divide-y divide-gray-800 border-t border-gray-800">
      <li
        v-for="book in filteredBooks"
        :key="book.id"
        class="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div class="flex-1 space-y-1">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="font-medium text-gray-100">{{ book.title }}</h3>
            <span
              v-if="book.has_audio === false"
              class="px-2 py-0.5 text-[11px] font-semibold bg-yellow-950/60 text-yellow-400 border border-yellow-800/60 rounded"
            >
              {{ t('incompleteAudio') }}
            </span>
          </div>
          <div class="text-sm text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
            <span>{{ book.total_paragraphs }} {{ t('paragraphs') }}</span>
            <span>{{ book.total_words }} {{ t('words') }}</span>
            <span>{{ t('dialogLabel') }} {{ (book.dialog_ratio * 100).toFixed(0) }}%</span>
          </div>
          <div class="text-xs text-gray-500">
            <span v-if="book.created_at">{{ t('createdLabel') }} {{ formatDate(book.created_at) }}</span>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 md:ml-auto">
          <!-- HTML5 Native Audio Player pointing to FastAPI endpoint -->
          <audio 
            v-if="book.has_audio !== false"
            controls 
            :src="`http://127.0.0.1:8000/book/${book.id}/download`" 
            preload="none" 
            class="h-8 max-w-[200px] outline-none"
          ></audio>

          <button
            v-if="book.has_audio !== false"
            @click="onDownload(book)"
            class="px-3 py-1.5 text-sm font-medium text-gray-100 bg-gray-800 border border-gray-700 rounded-lg hover:border-green-500 hover:text-green-400 transition-colors"
            title="Abrir carpeta de salida"
          >
            {{ t('openAudioBtn') }}
          </button>
          <button
            @click="onRegenerate(book)"
            class="px-3 py-1.5 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors"
          >
            {{ t('regenerateBtn') }}
          </button>
          <button
            @click="onDelete(book)"
            class="px-3 py-1.5 text-sm font-medium text-red-400 bg-gray-800 border border-gray-700 rounded-lg hover:border-red-500 hover:bg-red-500/10 transition-colors"
            title="Eliminar audiolibro"
          >
            🗑️ {{ t('deleteBtn') }}
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>