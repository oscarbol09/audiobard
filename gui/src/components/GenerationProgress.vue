<script setup lang="ts">
import { computed } from 'vue'
import { useGenerationStore } from '../stores/generation'
import { useI18nStore } from '../stores/i18n'

const generationStore = useGenerationStore()
const i18n = useI18nStore()
const { t } = i18n

const visible = computed(
  () =>
    generationStore.isGenerating ||
    generationStore.stage === 'complete' ||
    generationStore.stage === 'error' ||
    generationStore.stage === 'cancelled' ||
    generationStore.error !== null,
)

const stageLabel = computed(() => {
  const stage = generationStore.stage
  if (stage === 'parsing') return t('stageParsing')
  if (stage === 'characters' || stage === 'attribution') return t('stageAttribution')
  if (stage === 'voice_assignment') return t('stageVoice')
  if (stage === 'synthesis') return t('stageSynthesis')
  if (stage === 'complete') return t('stageComplete')
  return stage
})

const isError = computed(
  () => generationStore.stage === 'error' || generationStore.error !== null,
)

const isCancelled = computed(
  () => generationStore.stage === 'cancelled',
)

const isComplete = computed(
  () => generationStore.stage === 'complete' && generationStore.error === null,
)

const barColor = computed(() => {
  if (isError.value) return 'bg-red-500'
  if (isCancelled.value) return 'bg-gray-500'
  if (isComplete.value) return 'bg-green-500'
  return 'bg-brand-500'
})

async function onCancel(): Promise<void> {
  await generationStore.cancelGeneration()
}
</script>

<template>
  <section v-if="visible" class="space-y-3" aria-live="polite">
    <header class="flex items-baseline justify-between gap-4">
      <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-400">
        {{ stageLabel }}
      </h3>
      <div class="flex items-baseline gap-4">
        <span class="text-sm font-medium text-gray-300 tabular-nums">
          {{ generationStore.progress }}%
        </span>
        <button
          v-if="generationStore.isGenerating"
          type="button"
          class="rounded-md border border-gray-700 px-3 py-1 text-xs font-medium text-gray-300 hover:border-red-500 hover:text-red-400 transition-colors disabled:opacity-50"
          :disabled="generationStore.sessionId === null"
          @click="onCancel"
        >
          {{ t('cancelBtn') }}
        </button>
      </div>
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
      v-if="isCancelled"
      class="rounded-lg border border-gray-500/30 bg-gray-500/10 p-4 text-sm text-gray-400"
    >
      {{ generationStore.error ?? t('cancelled') }}
    </div>

    <div
      v-if="isComplete && generationStore.outputPath"
      class="rounded-lg border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-400"
    >
      <p>{{ t('stageComplete') }}</p>
      <code class="mt-1 block font-mono text-xs break-all">{{ generationStore.outputPath }}</code>
    </div>
  </section>
</template>
