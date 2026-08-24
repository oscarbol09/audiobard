import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGenerationStore = defineStore('generation', () => {
  const isGenerating = ref(false)
  const progress = ref(0)
  return { isGenerating, progress }
})
