<script setup lang="ts">
/**
 * Shows the sequential batch queue (issue #66): every dropped book with its
 * status, plus overall progress and a stopping button.
 */
import { useGenerationStore } from '../stores/generation'
import type { BatchQueueItem } from '../utils/batchQueue'

const generationStore = useGenerationStore()

const STATUS_STYLES: Record<BatchQueueItem['status'], string> = {
  pending: 'text-gray-400 border-gray-700',
  running: 'text-brand-400 border-brand-500/60',
  done: 'text-green-400 border-green-700',
  error: 'text-red-400 border-red-700',
  cancelled: 'text-yellow-400 border-yellow-700',
}

function statusLabel(item: BatchQueueItem): string {
  switch (item.status) {
    case 'pending':
      return 'Waiting'
    case 'running':
      return 'Generating'
    case 'done':
      return 'Done'
    case 'cancelled':
      return 'Cancelled'
    default:
      return item.error ? `Failed: ${item.error}` : 'Failed'
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="rounded-xl border border-gray-800 bg-gray-900/40 p-4 space-y-3">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-gray-100">Batch queue</h3>
        <p class="text-xs text-gray-500">
          {{ generationStore.queueSummary.done }} of {{ generationStore.queueSummary.total }} finished
          <span v-if="generationStore.queueSummary.failed > 0" class="text-red-400">
            · {{ generationStore.queueSummary.failed }} failed
          </span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs tabular-nums text-gray-400">{{ generationStore.queueSummary.percent }}%</span>
        <button
          type="button"
          class="px-3 py-1 text-xs font-medium text-gray-300 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-500 transition-colors disabled:opacity-40"
          :disabled="generationStore.queueRunning || generationStore.queue.length === 0"
          @click="generationStore.clearQueue()"
        >
          Clear
        </button>
      </div>
    </div>

    <div class="h-1.5 w-full rounded-full bg-gray-800 overflow-hidden">
      <div
        class="h-full bg-brand-500 transition-all duration-300"
        :style="{ width: `${generationStore.queueSummary.percent}%` }"
      />
    </div>

    <ul class="max-h-56 overflow-y-auto divide-y divide-gray-800">
      <li
        v-for="(item, index) in generationStore.queue"
        :key="item.id"
        class="py-2 flex items-center justify-between gap-3"
      >
        <div class="min-w-0 flex items-center gap-2">
          <span class="text-xs tabular-nums text-gray-500 w-5 text-right">{{ index + 1 }}</span>
          <div class="min-w-0">
            <p class="text-sm text-gray-200 truncate">{{ item.name }}</p>
            <p class="text-[11px] text-gray-500 truncate">{{ formatSize(item.size) }}</p>
          </div>
        </div>
        <span
          class="shrink-0 px-2 py-0.5 text-[11px] font-medium rounded border truncate max-w-[45%]"
          :class="STATUS_STYLES[item.status]"
        >
          {{ statusLabel(item) }}
        </span>
      </li>
    </ul>
  </div>
</template>
