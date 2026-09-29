<script setup lang="ts">
/**
 * Interactive player for a finished audiobook (issue #113).
 *
 * Two ways to get a waveform, chosen by file size so a long book can never
 * blow up the webview: books under `MAX_DECODE_BYTES` are decoded once with the
 * Web Audio API to draw every peak up front, larger books are sampled from an
 * analyser while they play, filling the timeline as it goes. If neither is
 * possible the native `<audio controls>` element is used instead.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  bucketIndexForRatio,
  chapterIndexAt,
  chapterRatios,
  computePeaks,
  downmix,
  formatClock,
  progressRatio,
  remainingSeconds,
  seekTimeFromOffset,
  type ChapterMarker,
} from '../utils/waveform'

const props = withDefaults(
  defineProps<{
    src: string
    title?: string
    chapters?: ChapterMarker[]
  }>(),
  { title: '', chapters: () => [] },
)

const BAR_COUNT = 160
const MAX_DECODE_BYTES = 60 * 1024 * 1024

const audioEl = ref<HTMLAudioElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const isPlaying = ref(false)
const loading = ref(false)
const peaksFailed = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const peaks = ref<number[]>(new Array(BAR_COUNT).fill(0))

const chapterTicks = computed(() => chapterRatios(props.chapters, duration.value))
const activeChapterIndex = computed(() => chapterIndexAt(props.chapters, currentTime.value))
const activeChapter = computed(() =>
  activeChapterIndex.value >= 0 ? props.chapters[activeChapterIndex.value] : null,
)

const elapsedLabel = computed(() => formatClock(currentTime.value))
const remainingLabel = computed(() => `-${formatClock(remainingSeconds(currentTime.value, duration.value))}`)
const playedRatio = computed(() => progressRatio(currentTime.value, duration.value))

let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let sourceNode: MediaElementAudioSourceNode | null = null
let animationFrame: number | null = null

function stopAnimation(): void {
  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame)
    animationFrame = null
  }
}

async function loadPeaks(): Promise<void> {
  peaksFailed.value = false
  loading.value = true
  stopAnimation()
  peaks.value = new Array(BAR_COUNT).fill(0)

  try {
    const response = await fetch(props.src)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const declaredSize = Number(response.headers.get('content-length') ?? 0)
    const buffer = await response.arrayBuffer()

    if (declaredSize > MAX_DECODE_BYTES || buffer.byteLength > MAX_DECODE_BYTES) {
      // Too long to decode in one go: sample it while it plays instead.
      startProgressivePeaks()
      return
    }

    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) throw new Error('Web Audio is unavailable')
    audioContext = audioContext ?? new Ctor()
    const decoded = await audioContext.decodeAudioData(buffer.slice(0))
    const channels = Array.from({ length: decoded.numberOfChannels }, (_, index) =>
      decoded.getChannelData(index),
    )
    peaks.value = computePeaks(downmix(channels, decoded.length), BAR_COUNT)
  } catch (error) {
    console.warn('Waveform peaks unavailable, falling back to the native player:', error)
    peaksFailed.value = true
  } finally {
    loading.value = false
    draw()
  }
}

/** Fill the timeline from the live signal while a long book plays. */
function startProgressivePeaks(): void {
  const audio = audioEl.value
  if (!audio) {
    peaksFailed.value = true
    return
  }
  try {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) throw new Error('Web Audio is unavailable')
    audioContext = audioContext ?? new Ctor()
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    sourceNode = audioContext.createMediaElementSource(audio)
    sourceNode.connect(analyser)
    analyser.connect(audioContext.destination)

    const data = new Uint8Array(analyser.fftSize)
    const sample = (): void => {
      if (analyser === null) return
      analyser.getByteTimeDomainData(data)
      let peak = 0
      for (let index = 0; index < data.length; index += 1) {
        peak = Math.max(peak, Math.abs(data[index] - 128) / 128)
      }
      const bucket = bucketIndexForRatio(progressRatio(audio.currentTime, audio.duration), BAR_COUNT)
      if (peak > peaks.value[bucket]) {
        const next = peaks.value.slice()
        next[bucket] = peak
        peaks.value = next
        draw()
      }
      animationFrame = requestAnimationFrame(sample)
    }
    animationFrame = requestAnimationFrame(sample)
  } catch (error) {
    console.warn('Progressive waveform unavailable:', error)
    peaksFailed.value = true
  }
}

function draw(): void {
  const canvas = canvasEl.value
  if (!canvas) return
  const context = canvas.getContext('2d')
  if (!context) return

  const width = canvas.width
  const height = canvas.height
  context.clearRect(0, 0, width, height)

  const barWidth = width / BAR_COUNT
  const playedX = playedRatio.value * width

  for (let index = 0; index < BAR_COUNT; index += 1) {
    const amplitude = Math.max(0.02, peaks.value[index] ?? 0)
    const barHeight = Math.max(2, amplitude * (height - 4))
    const x = index * barWidth
    context.fillStyle = x <= playedX ? '#38bdf8' : '#374151'
    context.fillRect(x, (height - barHeight) / 2, Math.max(1, barWidth - 1), barHeight)
  }

  context.fillStyle = 'rgba(148, 163, 184, 0.6)'
  for (const ratio of chapterTicks.value) {
    if (ratio <= 0) continue
    context.fillRect(Math.min(width - 1, ratio * width), 0, 1, height)
  }

  context.fillStyle = '#38bdf8'
  context.fillRect(Math.min(width - 2, playedX), 0, 2, height)
}

function togglePlay(): void {
  const audio = audioEl.value
  if (!audio) return
  if (audio.paused) {
    void audio.play().catch((error) => console.warn('Playback failed:', error))
  } else {
    audio.pause()
  }
}

function onSeek(event: MouseEvent): void {
  const audio = audioEl.value
  const canvas = canvasEl.value
  if (!audio || !canvas) return
  const target = seekTimeFromOffset(event.offsetX, canvas.width, duration.value)
  audio.currentTime = target
  currentTime.value = target
  draw()
}

function onKeydown(event: KeyboardEvent): void {
  const audio = audioEl.value
  if (!audio) return
  const step = event.shiftKey ? 30 : 5
  if (event.key === 'ArrowRight') {
    audio.currentTime = Math.min(duration.value, audio.currentTime + step)
  } else if (event.key === 'ArrowLeft') {
    audio.currentTime = Math.max(0, audio.currentTime - step)
  } else if (event.key === ' ' || event.key === 'Enter') {
    togglePlay()
  } else {
    return
  }
  event.preventDefault()
  currentTime.value = audio.currentTime
  draw()
}

function seekTo(seconds: number): void {
  const audio = audioEl.value
  if (!audio) return
  audio.currentTime = seconds
  currentTime.value = seconds
  draw()
}

function onTimeUpdate(): void {
  const audio = audioEl.value
  if (!audio) return
  currentTime.value = audio.currentTime
  draw()
}

function onLoadedMetadata(): void {
  const audio = audioEl.value
  if (!audio) return
  duration.value = Number.isFinite(audio.duration) ? audio.duration : 0
  draw()
}

function onPlay(): void {
  isPlaying.value = true
}

function onPause(): void {
  isPlaying.value = false
}

watch(() => props.src, () => {
  currentTime.value = 0
  duration.value = 0
  peaksFailed.value = false
  void loadPeaks()
})

watch(() => props.chapters, draw, { deep: true })

onMounted(() => {
  void loadPeaks()
})

onBeforeUnmount(() => {
  stopAnimation()
  analyser?.disconnect()
  sourceNode?.disconnect()
  void audioContext?.close()
  audioContext = null
})
</script>

<template>
  <div class="w-full max-w-md space-y-2">
    <div v-if="peaksFailed" class="flex items-center gap-2">
      <audio :src="src" controls preload="none" class="h-8 w-full" />
    </div>

    <template v-else>
      <audio
        ref="audioEl"
        :src="src"
        preload="metadata"
        class="hidden"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoadedMetadata"
        @play="onPlay"
        @pause="onPause"
        @ended="onPause"
      />

      <div class="flex items-center gap-2">
        <button
          type="button"
          @click="togglePlay"
          class="shrink-0 w-9 h-9 flex items-center justify-center rounded-full text-gray-900 bg-brand-500 hover:bg-brand-400 transition-colors"
          :aria-label="isPlaying ? 'Pause' : 'Play'"
        >
          <svg v-if="!isPlaying" class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
          </svg>
        </button>

        <canvas
          ref="canvasEl"
          width="640"
          height="56"
          class="flex-1 h-14 cursor-pointer rounded-lg bg-gray-900/60 border border-gray-800"
          role="slider"
          tabindex="0"
          aria-label="Audio waveform timeline"
          :aria-valuemin="0"
          :aria-valuemax="Math.round(duration)"
          :aria-valuenow="Math.round(currentTime)"
          @click="onSeek"
          @keydown="onKeydown"
        />
      </div>

      <div class="flex items-center justify-between text-[11px] text-gray-400">
        <span class="truncate max-w-[60%]">
          <template v-if="activeChapter">{{ activeChapter.title }}</template>
          <template v-else-if="loading">Building waveform…</template>
          <template v-else>{{ props.title }}</template>
        </span>
        <span class="tabular-nums">{{ elapsedLabel }} / {{ remainingLabel }}</span>
      </div>

      <ul v-if="props.chapters.length > 0" class="max-h-24 overflow-y-auto text-[11px] divide-y divide-gray-800 border-t border-gray-800">
        <li v-for="(chapter, index) in props.chapters" :key="`${chapter.start}-${index}`">
          <button
            type="button"
            @click="seekTo(chapter.start)"
            class="w-full text-left px-2 py-1 truncate transition-colors"
            :class="index === activeChapterIndex ? 'text-brand-400' : 'text-gray-400 hover:text-gray-200'"
          >
            {{ chapter.title }}
          </button>
        </li>
      </ul>
    </template>
  </div>
</template>
