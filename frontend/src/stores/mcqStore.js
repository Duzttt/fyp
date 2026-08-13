import { defineStore } from 'pinia'
import { ref } from 'vue'
import { generateMcq, getMcqHistory, submitMcqAttempt, deleteMcq } from '../services/api'

export const useMcqStore = defineStore('mcq', () => {
  // State
  const currentQuiz = ref(null)
  const quizHistory = ref([])
  const isGenerating = ref(false)
  const isLoading = ref(false)
  const error = ref(null)
  const lastConfig = ref(null)
  const lastResult = ref(null)

  // Actions
  async function loadHistory(limit = 20) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getMcqHistory(limit)
      quizHistory.value = response.quizzes || []
    } catch (err) {
      error.value = err.message
      console.error('Failed to load MCQ history:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function generate(documentIds, config = {}) {
    try {
      isGenerating.value = true
      error.value = null
      lastConfig.value = config
      lastResult.value = null

      const response = await generateMcq(documentIds, config)

      currentQuiz.value = {
        quiz_id: response.quiz_id,
        questions: response.questions || [],
        difficulty: response.difficulty,
        documents: response.documents || [],
      }

      return currentQuiz.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to generate MCQ quiz:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function submit(quizId, answers) {
    try {
      error.value = null
      const response = await submitMcqAttempt(quizId, answers)
      lastResult.value = {
        score: response.score,
        total: response.total,
        percentage: response.percentage,
        results: response.results || [],
      }
      return lastResult.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to submit MCQ attempt:', err)
      return null
    }
  }

  async function remove(quizId) {
    try {
      error.value = null
      await deleteMcq(quizId)

      quizHistory.value = quizHistory.value.filter((q) => q.id !== quizId)

      if (currentQuiz.value?.quiz_id === quizId) {
        currentQuiz.value = null
        lastResult.value = null
      }

      return true
    } catch (err) {
      error.value = err.message
      console.error('Failed to delete MCQ quiz:', err)
      return false
    }
  }

  function clearCurrent() {
    currentQuiz.value = null
    lastResult.value = null
  }

  return {
    currentQuiz,
    quizHistory,
    isGenerating,
    isLoading,
    error,
    lastConfig,
    lastResult,
    loadHistory,
    generate,
    submit,
    remove,
    clearCurrent,
  }
})
