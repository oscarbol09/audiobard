<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const healthOk = ref(false)
const healthError = ref<string | null>(null)
const checking = ref(true)

async function checkHealth() {
  checking.value = true
  healthError.value = null
  try {
    const ok = await invoke<boolean>('check_server_health')
    healthOk.value = ok
    if (!ok) {
      healthError.value = 'FastAPI server health check failed'
    }
  } catch (e) {
    healthError.value = e instanceof Error ? e.message : String(e)
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  // Retry health check every 2s until it passes
  const interval = setInterval(async () => {
    if (!healthOk.value) {
      await checkHealth()
    } else {
      clearInterval(interval)
    }
  }, 2000)

  // Initial check
  checkHealth()
})
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center p-6">
    <!-- Loading/Blocking Screen -->
    <div v-if="!healthOk" class="w-full max-w-md text-center space-y-6">
      <div class="space-y-4">
        <div class="inline-flex items-center justify-center">
          <svg class="animate-spin h-12 w-12 text-brand-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <div class="space-y-2">
          <h1 class="text-3xl font-extrabold tracking-tight text-brand-500">AudioBard</h1>
          <p class="text-gray-400" v-if="checking">Starting FastAPI server...</p>
          <p class="text-gray-400" v-else-if="healthError">Health check failed: {{ healthError }}</p>
          <p class="text-gray-400" v-else>Waiting for server...</p>
        </div>
        <div v-if="healthError" class="text-sm text-red-400">
          Retrying in 2 seconds...
        </div>
      </div>
    </div>

    <!-- Main App Content (shown after health check passes) -->
    <div v-else class="w-full max-w-4xl space-y-6">
      <header class="flex items-center justify-between">
        <h1 class="text-3xl font-extrabold tracking-tight text-brand-500">AudioBard</h1>
        <span class="px-3 py-1 text-xs font-medium text-green-400 bg-green-900/30 rounded-full">
          Server Ready
        </span>
      </header>
      <main class="space-y-6">
        <p class="text-gray-400">
          FastAPI server is healthy. Ready to generate audiobooks.
        </p>
        <!-- Main app content will go here in future commits -->
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Ensure full height */
html, body, #app {
  height: 100%;
}
</style>