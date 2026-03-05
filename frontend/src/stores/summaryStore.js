import { defineStore } from 'pinia'
import { ref } from 'vue'
import { generateSummary, getSummaryHistory, deleteSummary, regenerateSummary } from '../services/api'

export const useSummaryStore = defineStore('summary', () => {
  // State
  const currentSummary = ref(null)
  const summaryHistory = ref([])
  const isLoading = ref(false)
  const isGenerating = ref(false)
  const error = ref(null)
  const lastConfig = ref(null)

  // Actions
  async function loadHistory(limit = 20) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getSummaryHistory(limit)
      summaryHistory.value = response.history || []
    } catch (err) {
      error.value = err.message
      console.error('Failed to load summary history:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function generate(documentIds, config = {}) {
    try {
      isGenerating.value = true
      error.value = null
      lastConfig.value = config

      const response = await generateSummary(documentIds, config)
      
      currentSummary.value = {
        text: response.summary,
        citations: response.citations || [],
        comparison: response.comparison || [],
        document_count: response.document_count,
        documents: response.documents,
        history_id: response.history_id,
      }

      // Add to history
      summaryHistory.value.unshift({
        id: response.history_id,
        timestamp: new Date().toISOString(),
        documents: response.documents,
        summary: response.summary,
        config,
      })

      return currentSummary.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to generate summary:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function regenerate(historyId, newConfig = {}) {
    try {
      isGenerating.value = true
      error.value = null

      const response = await regenerateSummary(historyId, newConfig)
      
      currentSummary.value = {
        text: response.summary,
        citations: response.citations || [],
        comparison: response.comparison || [],
        config: response.config,
      }

      // Update history entry
      const idx = summaryHistory.value.findIndex(h => h.id === historyId)
      if (idx !== -1) {
        summaryHistory.value[idx] = {
          ...summaryHistory.value[idx],
          summary: response.summary,
          config: response.config,
          regenerated_at: new Date().toISOString(),
        }
      }

      return currentSummary.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to regenerate summary:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function remove(summaryId) {
    try {
      error.value = null
      await deleteSummary(summaryId)
      
      // Remove from history
      summaryHistory.value = summaryHistory.value.filter(h => h.id !== summaryId)
      
      // Clear current if it's the same
      if (currentSummary.value?.history_id === summaryId) {
        currentSummary.value = null
      }
      
      return true
    } catch (err) {
      error.value = err.message
      console.error('Failed to delete summary:', err)
      return false
    }
  }

  function clearCurrent() {
    currentSummary.value = null
    error.value = null
  }

  function selectFromHistory(summary) {
    currentSummary.value = {
      text: summary.summary,
      citations: summary.citations || [],
      comparison: summary.comparison || [],
      document_count: summary.document_count,
      documents: summary.documents,
      history_id: summary.id,
      config: summary.config,
    }
  }

  return {
    // State
    currentSummary,
    summaryHistory,
    isLoading,
    isGenerating,
    error,
    lastConfig,
    // Actions
    loadHistory,
    generate,
    regenerate,
    remove,
    clearCurrent,
    selectFromHistory,
  }
})
