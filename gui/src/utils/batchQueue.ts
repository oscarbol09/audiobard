/**
 * Pure state machine behind the drag & drop batch queue (issue #66).
 *
 * The Tauri side of the app is not importable from a test runner, so the queue
 * rules live here as plain functions over plain data: add, pick the next item,
 * transition, and summarise.
 */

export type QueueItemStatus = 'pending' | 'running' | 'done' | 'error' | 'cancelled'

export interface BatchQueueItem {
  id: string
  name: string
  size: number
  file: File
  status: QueueItemStatus
  error?: string
}

export interface QueueSummary {
  total: number
  pending: number
  running: number
  done: number
  failed: number
  cancelled: number
  /** Completed share of the queue, 0..100, counting failures as finished. */
  percent: number
}

export type IdFactory = () => string

export interface FileLike {
  name: string
  size: number
  file: File
}

/** Build queue items for freshly dropped files, skipping duplicates of `existing`. */
export function createQueueItems(
  files: FileLike[],
  existing: BatchQueueItem[] = [],
  createId: IdFactory = defaultIdFactory,
): BatchQueueItem[] {
  const seen = new Set(existing.map((item) => `${item.name}:${item.size}`))
  const items: BatchQueueItem[] = []
  for (const file of files) {
    const key = `${file.name}:${file.size}`
    if (seen.has(key)) continue
    seen.add(key)
    items.push({
      id: createId(),
      name: file.name,
      size: file.size,
      file: file.file,
      status: 'pending',
    })
  }
  return items
}

/** The item the worker should pick up next: the first still pending one. */
export function nextPendingItem(items: BatchQueueItem[]): BatchQueueItem | null {
  return items.find((item) => item.status === 'pending') ?? null
}

/** Immutably update one item's status. */
export function markItem(
  items: BatchQueueItem[],
  id: string,
  status: QueueItemStatus,
  error?: string,
): BatchQueueItem[] {
  return items.map((item) =>
    item.id === id ? { ...item, status, error: error ?? item.error } : item,
  )
}

/** Mark every still-pending item cancelled, used when the user stops the queue. */
export function cancelPending(items: BatchQueueItem[]): BatchQueueItem[] {
  return items.map((item) =>
    item.status === 'pending' ? { ...item, status: 'cancelled' as QueueItemStatus } : item,
  )
}

export function summarize(items: BatchQueueItem[]): QueueSummary {
  const count = (status: QueueItemStatus): number =>
    items.filter((item) => item.status === status).length
  const done = count('done')
  const failed = count('error')
  const cancelled = count('cancelled')
  const total = items.length
  const finished = done + failed + cancelled
  return {
    total,
    pending: count('pending'),
    running: count('running'),
    done,
    failed,
    cancelled,
    percent: total === 0 ? 0 : Math.round((finished / total) * 100),
  }
}

/** True when nothing is left to process. */
export function isQueueFinished(items: BatchQueueItem[]): boolean {
  return items.every((item) => item.status !== 'pending' && item.status !== 'running')
}

export function defaultIdFactory(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '')
  }
  return `q${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}
