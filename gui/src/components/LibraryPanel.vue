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
}

const books = ref<LibraryBook[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const searchQuery = ref('')

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
  if (!searchQuery.value) return books.value
  const q = searchQuery.value.toLowerCase()
  return books.value.filter((b) => b.title.toLowerCase().includes(q))
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
  if (!iso) return 'Unknown'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, {
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
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold tracking-tight text-gray-100">{{ t('libraryTitle') }}</h2>
      <div class="flex items-center gap-3">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search books..."
          class="px-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded-lg focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-shadow w-48"
        />
        <button
          @click="loadLibrary"
          class="px-3 py-1.5 text-sm font-medium text-brand-400 bg-brand-500/10 hover:bg-brand-500/20 rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-center py-8 text-gray-400">Loading library...</div>
    <div v-else-if="error" class="text-center py-8 text-red-400">{{ error }}</div>
    <div v-else-if="filteredBooks.length === 0" class="text-center py-12 border-2 border-dashed border-gray-800 rounded-xl">
      <p class="text-gray-400">{{ searchQuery ? 'No books match your search.' : t('noBooks') }}</p>
    </div>
    
    <ul v-else class="divide-y divide-gray-800 border-t border-gray-800">
      <li
        v-for="book in filteredBooks"
        :key="book.id"
        class="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div class="flex-1 space-y-1">
          <h3 class="font-medium text-gray-100">{{ book.title }}</h3>
          <div class="text-sm text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
            <span>{{ book.total_paragraphs }} paragraphs</span>
            <span>{{ book.total_words }} words</span>
            <span>Dialog: {{ (book.dialog_ratio * 100).toFixed(0) }}%</span>
          </div>
          <div class="text-xs text-gray-500">
            <span v-if="book.created_at">Created: {{ formatDate(book.created_at) }}</span>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 md:ml-auto">
          <!-- HTML5 Native Audio Player pointing to FastAPI endpoint -->
          <audio 
            controls 
            :src="`http://127.0.0.1:8000/book/${book.id}/download`" 
            preload="none" 
            class="h-8 max-w-[200px] outline-none"
          ></audio>

          <button
            @click="onDownload(book)"
            class="px-3 py-1.5 text-sm font-medium text-gray-100 bg-gray-800 border border-gray-700 rounded-lg hover:border-green-500 hover:text-green-400 transition-colors"
            title="Abrir carpeta de salida"
          >
            Abrir Audio
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