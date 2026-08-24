<script setup lang="ts">
import { computed } from 'vue'
import { useGenerationStore } from '../stores/generation'

const generationStore = useGenerationStore()

const STAGE_LABELS: Record<string, string> = {
  idle: 'Idle',
  queued: 'Starting',
  parsing: 'Parsing book',
  characters: 'Extracting characters',
  voice_assignment: 'Mapping voices',
  synthesis: 'Synthesising speech',
  assembly: 'Assembling audio',
  complete: 'Complete',
  error: 'Error',
}

const visible = computed(
  () =>
    generationStore.isGenerating ||
    generationStore.stage === 'complete' ||
    generationStore.stage === 'error' ||
    generationStore.error !== null,
)

const stageLabel = computed(
  () => STAGE_LABELS[generationStore.stage] ?? generationStore.stage,
)

const isError = computed(
  () => generationStore.stage === 'error' || generationStore.error !== null,
)

const isComplete = computed(
  () => generationStore.stage === 'complete' && generationStore.error === null,
)

const barColor = computed(() => {
  if (isError.value) return 'bg-red-500'
  if (isComplete.value) return 'bg-green-500'
  return 'bg-brand-500'
})
</script>

<template>
  <section v-if="visible" class="space-y-3" aria-live="polite">
    <header class="flex items-baseline justify-between gap-4">
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-400">
        {{ stageLabel }}
    </h3>
      <span class="text-sm font-medium text-gray-300 tabular-nums">
        {{ generationStore.progress }}%
    </span>
  </header>

    <div
      class="h-2 w-full rounded-full bg-gray-800 overflow-hidden"
      role="progressbar"
      :aria-valuenow="generationStore.progress"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="`Generation progress: ${generationStore.progress} percent`"
    >
      <div
        class="h-full transition-all duration-300"
        :class="barColor"
        :style="{ width: `${generationStore.progress}%` }"
      />
  </div>

    <p v-if="generationStore.message" class="text-sm text-gray-300">
      {{ generationStore.message }}
  </p>

    <div
      v-if="isError"
      class="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400"
    >
      {{ generationStore.error ?? 'Generation failed.' }}
  </div>

    <div
      v-if="isComplete && generationStore.outputPath"
      class="rounded-lg border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-400"
    >
      <p>Audiobook saved to</p>
      <code class="mt-1 block font-mono text-xs break-all">{{ generationStore.outputPath }}</code>
  </div>
</section>
</template>
