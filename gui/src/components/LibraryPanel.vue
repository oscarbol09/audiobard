<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useI18nStore } from '../stores/i18n'

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
  if (!searchQuery.value.trim()) return books.value
  const q = searchQuery.value.toLowerCase()
  return books.value.filter(
    (b) =>
      b.title.toLowerCase().includes(q) ||
      b.path.toLowerCase().includes(q)
  )
})

async function onDownload(book: LibraryBook) {
  try {
    const path = await invoke<string>('download_book', { bookId: book.id, book_id: book.id })
    // Open file with system default player
    await invoke('shell.open', { path })
  } catch (e) {
    console.error('Download failed:', e)
    alert(`Failed to download: ${e instanceof Error ? e.message : String(e)}`)
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
    <header class="flex items-center justify-between gap-4">
      <h2 class="text-xl font-semibold text-gray-100">{{ t('libraryTitle') }}</h2>
      <div class="flex items-center gap-2">
        <input
          type="text"
          v-model="searchQuery"
          placeholder="Search books..."
          class="w-64 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
        />
        <button
          @click="loadLibrary"
          :disabled="loading"
          class="px-4 py-2 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors disabled:opacity-50"
        >
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
      {{ error }}
    </div>

    <div v-if="loading" class="flex justify-center py-8">
      <svg class="animate-spin h-8 w-8 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>

    <div v-else-if="filteredBooks.length === 0" class="text-center py-12 text-gray-500">
      <svg class="mx-auto h-12 w-12 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
      </svg>
      <p class="mt-2 text-sm">{{ searchQuery ? 'No books match your search.' : t('noBooks') }}</p>
    </div>

    <ul v-else class="divide-y divide-gray-800">
      <li
        v-for="book in filteredBooks"
        :key="book.id"
        class="py-4 flex flex-col md:flex-row md:items-center gap-4"
      >
        <div class="flex-1 min-w-0">
          <h3 class="font-medium text-gray-100 truncate">{{ book.title }}</h3>
          <div class="flex flex-wrap gap-4 text-sm text-gray-500 mt-1">
            <span>{{ book.total_paragraphs }} paragraphs</span>
            <span>{{ book.total_words.toLocaleString() }} words</span>
            <span>Dialog: {{ (book.dialog_ratio * 100).toFixed(0) }}%</span>
            <span v-if="book.created_at">Created: {{ formatDate(book.created_at) }}</span>
          </div>
        </div>

        <div class="flex flex-wrap gap-2 md:ml-auto">
          <button
            @click="onDownload(book)"
            class="px-3 py-1.5 text-sm font-medium text-gray-100 bg-gray-800 border border-gray-700 rounded-lg hover:border-green-500 hover:text-green-400 transition-colors"
          >
            {{ t('downloadBtn') }}
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