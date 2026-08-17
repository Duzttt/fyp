import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  generateFlashcards,
  getFlashcardsHistory,
  deleteFlashcards,
} from '../services/api'

export const useFlashcardStore = defineStore('flashcard', () => {
  const currentDeck = ref(null)
  const deckHistory = ref([])
  const isLoading = ref(false)
  const isGenerating = ref(false)
  const error = ref(null)

  async function loadHistory(limit = 20) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getFlashcardsHistory(limit)
      deckHistory.value = response.history || []
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to load flashcard history:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function generate(documentIds, config = {}) {
    try {
      isGenerating.value = true
      error.value = null
      const response = await generateFlashcards(documentIds, config)

      currentDeck.value = {
        deck_id: response.deck_id,
        cards: response.cards || [],
        config: response.config,
        documents: response.documents || [],
      }

      deckHistory.value.unshift({
        id: response.deck_id,
        timestamp: new Date().toISOString(),
        documents: response.documents || [],
        cards: response.cards || [],
        card_count: (response.cards || []).length,
        config: response.config,
      })

      return currentDeck.value
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to generate flashcards:', err)
      return null
    } finally {
      isGenerating.value = false
    }
  }

  async function remove(deckId) {
    try {
      error.value = null
      await deleteFlashcards(deckId)

      deckHistory.value = deckHistory.value.filter((h) => h.id !== deckId)

      if (currentDeck.value?.deck_id === deckId) {
        currentDeck.value = null
      }

      return true
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      console.error('Failed to delete flashcards:', err)
      return false
    }
  }

  function selectFromHistory(deck) {
    currentDeck.value = {
      deck_id: deck.id,
      cards: deck.cards || [],
      config: deck.config,
      documents: deck.documents || [],
    }
  }

  function clearCurrent() {
    currentDeck.value = null
    error.value = null
  }

  return {
    currentDeck,
    deckHistory,
    isLoading,
    isGenerating,
    error,
    loadHistory,
    generate,
    remove,
    selectFromHistory,
    clearCurrent,
  }
})
