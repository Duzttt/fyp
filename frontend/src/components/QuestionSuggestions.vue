<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getQuestionSuggestions, recordSuggestionClick } from '../services/api'

const props = defineProps({
  selectedDocuments: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['question-select'])

const suggestions = ref([])
const isLoading = ref(false)
const error = ref('')
const isRefreshing = ref(false)
const hasLoadedOnce = ref(false)

// Computed
const hasSuggestions = computed(() => suggestions.value.length > 0)
const hasSelection = computed(() => props.selectedDocuments.length > 0)
const canGenerate = computed(() => hasSelection.value && !isLoading.value && !props.disabled)

// Watch for document selection changes
watch(
  () => props.selectedDocuments,
  async (newDocs, oldDocs) => {
    // Only auto-generate if documents changed and we haven't loaded yet
    if (newDocs.length > 0 && newDocs !== oldDocs && !hasLoadedOnce.value) {
      await generateSuggestions()
    } else if (newDocs.length === 0) {
      // Clear suggestions when no documents selected
      suggestions.value = []
      error.value = ''
    }
  },
  { deep: true }
)

// Generate suggestions based on selected documents
const generateSuggestions = async () => {
  if (!canGenerate.value) return

  isLoading.value = true
  error.value = ''

  try {
    const docIds = props.selectedDocuments.map(doc => doc.name || doc.filename)
    
    const response = await getQuestionSuggestions(docIds)
    
    if (response.success && response.suggestions) {
      suggestions.value = response.suggestions.map((text, index) => ({
        id: `suggestion_${Date.now()}_${index}`,
        text,
        position: index,
      }))
      hasLoadedOnce.value = true
    } else {
      error.value = response.message || 'Failed to generate suggestions'
    }
  } catch (err) {
    console.error('Failed to generate suggestions:', err)
    error.value = err.response?.data?.detail || err.message || 'Failed to generate suggestions'
    
    // Fallback: generate simple template-based suggestions
    generateFallbackSuggestions()
  } finally {
    isLoading.value = false
  }
}

// Fallback suggestions when LLM fails
const generateFallbackSuggestions = () => {
  const docNames = props.selectedDocuments.map(doc => doc.name || doc.filename)
  
  if (docNames.length === 0) return
  
  const mainDoc = docNames[0]
  const docName = mainDoc.replace('.pdf', '')
  
  // Simple template-based fallback
  suggestions.value = [
    {
      id: `fallback_${Date.now()}_0`,
      text: `What is the main topic covered in ${docName}?`,
      position: 0,
    },
    {
      id: `fallback_${Date.now()}_1`,
      text: `Explain the key concepts from ${docName}.`,
      position: 1,
    },
    {
      id: `fallback_${Date.now()}_2`,
      text: `What are the most important points in ${docName}?`,
      position: 2,
    },
  ]
  hasLoadedOnce.value = true
}

// Handle suggestion click
const handleSuggestionClick = async (suggestion) => {
  // Emit the question to parent
  emit('question-select', suggestion.text)
  
  // Record click for analytics
  try {
    const docIds = props.selectedDocuments.map(doc => doc.name || doc.filename)
    await recordSuggestionClick(suggestion.text, docIds, suggestion.position)
  } catch (err) {
    console.error('Failed to record suggestion click:', err)
    // Don't show error to user - this is just analytics
  }
}

// Refresh suggestions manually
const handleRefresh = async () => {
  if (!canGenerate.value) return
  
  isRefreshing.value = true
  await generateSuggestions()
  isRefreshing.value = false
}

// Expose methods for parent component
defineExpose({
  generateSuggestions,
  refresh: handleRefresh,
})

onMounted(() => {
  // Auto-generate on mount if documents are selected
  if (hasSelection.value) {
    generateSuggestions()
  }
})
</script>

<template>
  <div class="question-suggestions" :class="{ 'disabled': disabled || !hasSelection }">
    <!-- Header -->
    <div class="suggestions-header">
      <div class="header-title">
        <span class="title-icon">💡</span>
        <span class="title-text">Suggested Questions</span>
      </div>
      
      <button
        v-if="hasSuggestions || isLoading"
        class="refresh-btn"
        @click="handleRefresh"
        :disabled="isRefreshing || !hasSelection"
        title="Refresh suggestions"
      >
        <span class="refresh-icon" :class="{ 'spinning': isRefreshing }">↻</span>
      </button>
    </div>
    
    <!-- Loading State -->
    <div v-if="isLoading" class="suggestions-loading">
      <div class="loading-spinner"></div>
      <span class="loading-text">Generating smart questions...</span>
    </div>
    
    <!-- Error State -->
    <div v-else-if="error && !hasSuggestions" class="suggestions-error">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{{ error }}</span>
    </div>
    
    <!-- No Selection State -->
    <div v-else-if="!hasSelection" class="suggestions-no-selection">
      <span class="no-selection-icon">📄</span>
      <span class="no-selection-text">Select documents to see suggestions</span>
    </div>
    
    <!-- Suggestions List -->
    <div v-else-if="hasSuggestions" class="suggestions-list">
      <div
        v-for="(suggestion, index) in suggestions"
        :key="suggestion.id"
        class="suggestion-card"
        @click="handleSuggestionClick(suggestion)"
        :style="{ animationDelay: `${index * 0.1}s` }"
      >
        <div class="suggestion-number">{{ index + 1 }}</div>
        <div class="suggestion-text">{{ suggestion.text }}</div>
        <div class="suggestion-hover-indicator">
          <span>Click to ask →</span>
        </div>
      </div>
    </div>
    
    <!-- Empty State (shouldn't normally show) -->
    <div v-else class="suggestions-empty">
      <span class="empty-icon">🤔</span>
      <span class="empty-text">No suggestions available</span>
    </div>
  </div>
</template>

<style scoped>
.question-suggestions {
  background: linear-gradient(
    135deg,
    rgba(15, 25, 45, 0.5) 0%,
    rgba(25, 35, 60, 0.6) 100%
  );
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(15px) saturate(180%);
  -webkit-backdrop-filter: blur(15px) saturate(180%);
  padding: 12px;
  transition: all 0.3s ease;
}

.question-suggestions.disabled {
  opacity: 0.6;
  pointer-events: none;
}

/* Header */
.suggestions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding: 0 4px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.title-icon {
  font-size: 14px;
}

.refresh-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
  color: white;
}

.refresh-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.refresh-icon {
  font-size: 14px;
  transition: transform 0.3s;
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

/* Loading State */
.suggestions-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  gap: 10px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid rgba(99, 102, 241, 0.3);
  border-top-color: var(--accent);
  animation: spin 1s linear infinite;
}

.loading-text {
  font-size: 11px;
  color: var(--text-muted);
}

/* Error State */
.suggestions-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  font-size: 11px;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.error-icon {
  font-size: 14px;
}

/* No Selection State */
.suggestions-no-selection {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.no-selection-icon {
  font-size: 20px;
  opacity: 0.6;
}

/* Suggestions List */
.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  animation: slideIn 0.3s ease forwards;
  animation-fill-mode: both;
  opacity: 0;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.suggestion-card:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: var(--accent);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.suggestion-number {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(139, 92, 246, 0.4));
  border: 1px solid rgba(99, 102, 241, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
}

.suggestion-text {
  flex: 1;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-main);
  padding-top: 2px;
}

.suggestion-hover-indicator {
  position: absolute;
  right: 12px;
  bottom: 8px;
  font-size: 10px;
  color: var(--accent);
  opacity: 0;
  transform: translateX(-5px);
  transition: all 0.2s;
}

.suggestion-card:hover .suggestion-hover-indicator {
  opacity: 1;
  transform: translateX(0);
}

/* Empty State */
.suggestions-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  font-size: 20px;
  opacity: 0.5;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
