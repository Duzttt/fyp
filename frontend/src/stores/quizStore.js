import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  generateQuiz,
  submitQuiz,
  getQuizHistory,
  deleteQuiz,
} from '../services/api'

export const useQuizStore = defineStore('quiz', () => {
  const currentQuiz = ref(null)
  const quizHistory = ref([])
  const isLoading = ref(false)
  const isGenerating = ref(false)
  const isSubmitting = ref(false)
  const lastResult = ref(null)
  const error = ref(null)

  async function loadHistory(limit = 20) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getQuizHistory(limit)
      quizHistory.value = response.history || []
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to load quiz history:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function generate(documentIds, config = {}) {
    try {
      isGenerating.value = true
      error.value = null
      const response = await generateQuiz(documentIds, config)

      currentQuiz.value = {
        quiz_id: response.quiz_id,
        questions: response.questions || [],
        config: response.config,
        documents: response.documents || [],
        attempts: [],
      }
      lastResult.value = null

      quizHistory.value.unshift({
        id: response.quiz_id,
        timestamp: new Date().toISOString(),
        documents: response.documents || [],
        questions: response.questions || [],
        config: response.config,
        attempts: [],
      })

      return currentQuiz.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to generate quiz:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function submit(answers) {
    if (!currentQuiz.value) return null
    try {
      isSubmitting.value = true
      error.value = null
      const response = await submitQuiz(currentQuiz.value.quiz_id, answers)

      lastResult.value = {
        score: response.score,
        total: response.total,
        per_question: response.per_question || [],
      }

      return lastResult.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to submit quiz:', err)
      return null
    } finally {
      isSubmitting.value = false
    }
  }

  async function remove(quizId) {
    try {
      error.value = null
      await deleteQuiz(quizId)

      quizHistory.value = quizHistory.value.filter((h) => h.id !== quizId)

      if (currentQuiz.value?.quiz_id === quizId) {
        currentQuiz.value = null
      }

      return true
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to delete quiz:', err)
      return false
    }
  }

  function selectFromHistory(quiz) {
    currentQuiz.value = {
      quiz_id: quiz.id,
      questions: quiz.questions || [],
      config: quiz.config,
      documents: quiz.documents || [],
      attempts: quiz.attempts || [],
    }
    lastResult.value = null
  }

  function clearCurrent() {
    currentQuiz.value = null
    lastResult.value = null
    error.value = null
  }

  return {
    currentQuiz,
    quizHistory,
    isLoading,
    isGenerating,
    isSubmitting,
    lastResult,
    error,
    loadHistory,
    generate,
    submit,
    remove,
    selectFromHistory,
    clearCurrent,
  }
})
