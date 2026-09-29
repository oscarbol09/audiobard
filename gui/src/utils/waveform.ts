/**
 * Pure helpers behind the Library waveform player (issue #113).
 *
 * Everything here is framework free so the geometry and time maths can be
 * reasoned about — and tested — without a browser.
 */

export interface ChapterMarker {
  title: string
  /** Start of the chapter in seconds. */
  start: number
  /** End of the chapter in seconds. */
  end: number
}

/** Reduce mono samples (-1..1) to `buckets` peak amplitudes (0..1). */
export function computePeaks(samples: ArrayLike<number>, buckets: number): number[] {
  const size = Math.max(1, Math.floor(buckets))
  const peaks: number[] = new Array(size).fill(0)
  const total = samples.length
  if (total === 0) return peaks

  const step = total / size
  for (let bucket = 0; bucket < size; bucket += 1) {
    const start = Math.floor(bucket * step)
    const end = bucket === size - 1 ? total : Math.floor((bucket + 1) * step)
    let peak = 0
    for (let index = start; index < end; index += 1) {
      const value = Math.abs(samples[index])
      if (value > peak) peak = value
    }
    peaks[bucket] = Math.min(1, peak)
  }
  return peaks
}

/** Downmix planar float channels to a single mono channel. */
export function downmix(channels: ArrayLike<number>[], length: number): Float32Array {
  const mono = new Float32Array(length)
  if (channels.length === 0) return mono
  for (let channel = 0; channel < channels.length; channel += 1) {
    const samples = channels[channel]
    for (let index = 0; index < length && index < samples.length; index += 1) {
      mono[index] += samples[index]
    }
  }
  for (let index = 0; index < length; index += 1) {
    mono[index] /= channels.length
  }
  return mono
}

/** Format seconds as `m:ss`, or `h:mm:ss` once the book is longer than an hour. */
export function formatClock(seconds: number): string {
  const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0
  const total = Math.floor(safe)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const pad = (value: number): string => String(value).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`
}

/** Bucket a 0..1 playback ratio lands in, for progressive peak building. */
export function bucketIndexForRatio(ratio: number, buckets: number): number {
  if (buckets <= 0) return 0
  return Math.min(buckets - 1, Math.floor(clampRatio(ratio) * buckets))
}

/** Clamp a 0..1 ratio. */
export function clampRatio(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(1, Math.max(0, value))
}

/** Map a pointer position on the waveform to a playback time in seconds. */
export function seekTimeFromOffset(
  offsetX: number,
  width: number,
  duration: number,
): number {
  if (!(width > 0) || !(duration > 0) || !Number.isFinite(duration)) return 0
  return clampRatio(offsetX / width) * duration
}

/** Playback progress as a 0..1 ratio. */
export function progressRatio(currentTime: number, duration: number): number {
  if (!(duration > 0) || !Number.isFinite(currentTime)) return 0
  return clampRatio(currentTime / duration)
}

/** Index of the chapter containing `time`, or -1 when there are no chapters. */
export function chapterIndexAt(chapters: ChapterMarker[], time: number): number {
  let index = -1
  for (let position = 0; position < chapters.length; position += 1) {
    if (time + 1e-6 >= chapters[position].start) index = position
  }
  return index
}

/** Chapter starts as 0..1 ratios, for drawing the chapter ticks. */
export function chapterRatios(chapters: ChapterMarker[], duration: number): number[] {
  if (!(duration > 0)) return []
  return chapters.map((chapter) => clampRatio(chapter.start / duration))
}

/** Remaining playback time in seconds, never negative. */
export function remainingSeconds(currentTime: number, duration: number): number {
  if (!Number.isFinite(duration) || duration <= 0) return 0
  return Math.max(0, duration - Math.max(0, currentTime))
}
