<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue: File | null
  acceptedTypes: string[]
  maxSizeMB: number
}

interface Emits {
  (e: 'update:modelValue', file: File | null): void
  (e: 'error', message: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const isDragging = ref(false)
const dragError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const acceptedTypesDisplay = computed(() =>
  props.acceptedTypes.map(t => `.${t}`).join(', ')
)

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function validateFile(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!extension || !props.acceptedTypes.includes(extension)) {
    return `Invalid file type. Accepted: ${props.acceptedTypes.join(', ')}`
  }

  const maxBytes = props.maxSizeMB * 1024 * 1024
  if (file.size > maxBytes) {
    return `File too large. Maximum size: ${props.maxSizeMB} MB`
  }

  return null
}

function handleFile(file: File) {
  dragError.value = null
  const error = validateFile(file)
  if (error) {
    dragError.value = error
    emit('error', error)
    return
  }
  emit('update:modelValue', file)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false

  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    handleFile(input.files[0])
  }
  input.value = ''
}

function clearFile() {
  emit('update:modelValue', null)
  dragError.value = null
}

function triggerFileInput() {
  fileInput.value?.click()
}
</script>

<template>
  <div class="w-full max-w-2xl mx-auto">
    <!-- Drop Zone -->
    <div
      class="relative rounded-xl border-2 transition-all duration-200"
      :class="[
        'border-gray-700 bg-gray-900/50',
        isDragging ? 'border-brand-500 bg-brand-500/10' : 'border-dashed',
        dragError ? 'border-red-500 bg-red-500/10' : ''
      ]"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <!-- Hidden file input -->
      <input
        ref="fileInput"
        type="file"
        class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        :accept="acceptedTypesDisplay"
        @change="onFileSelect"
        aria-label="Select book file"
      />

      <!-- Drop zone content -->
      <div class="p-8 text-center space-y-4">
        <!-- Upload icon -->
        <div
          class="inline-flex items-center justify-center w-16 h-16 rounded-full mx-auto"
          :class="[
            'text-2xl',
            dragError ? 'text-red-500 bg-red-500/10' :
            isDragging ? 'text-brand-500 bg-brand-500/10' :
            'text-gray-500 bg-gray-800'
          ]"
        >
          <svg
            class="w-8 h-8"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 0115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            ></path>
          </svg>
        </div>

        <!-- Text content -->
        <div class="space-y-2">
          <p class="text-lg font-medium text-gray-100">
            {{
              dragError
                ? 'Invalid file - see error below'
                : isDragging
                ? 'Drop the file here'
                : 'Drag & drop your book here, or click to select'
            }}
          </p>
          <p class="text-sm text-gray-500">
            Accepted: {{ acceptedTypesDisplay }} • Max {{ props.maxSizeMB }} MB
          </p>
        </div>

        <!-- Hidden file input trigger -->
        <button
          type="button"
          class="mt-4 px-4 py-2 text-sm font-medium text-gray-900 bg-brand-500 hover:bg-brand-400 rounded-lg transition-colors"
          @click="triggerFileInput"
        >
          Click to Select File
        </button>
      </div>

      <!-- Hidden file input -->
      <input
        ref="fileInput"
        type="file"
        class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        :accept="acceptedTypesDisplay"
        @change="onFileSelect"
        aria-label="Select book file"
      />
    </div>

    <!-- Error message -->
    <div v-if="dragError" class="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-3.293 3.293a1 1 0 101.414 1.414L10 11.414l3.293 3.293a1 1 0 001.414-1.414L11.414 10l3.293 3.293a1 1 0 001.414-1.414L10 8.586 6.707 6.707a1 1 0 00-1.414 1.414l3 3z" clip-rule="evenodd"></path>
        </svg>
        <span>{{ dragError }}</span>
      </div>
    </div>

    <!-- Selected file preview -->
    <div v-if="props.modelValue" class="mt-6 p-4 rounded-lg bg-gray-800/50 border border-gray-700">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <svg class="w-8 h-8 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2h7"></path>
          </svg>
          <div>
            <p class="font-medium text-gray-100 truncate max-w-xs">{{ props.modelValue.name }}</p>
            <p class="text-sm text-gray-500">{{ formatFileSize(props.modelValue.size) }}</p>
          </div>
        </div>
        <button
          type="button"
          @click="clearFile"
          class="p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
          aria-label="Remove file"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>