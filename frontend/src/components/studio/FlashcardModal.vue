<script setup>
import { ref, computed, watch } from 'vue'
import { useFlashcardStore } from '../../stores/flashcardStore'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'close', 'generate', 'view'])

const flashcardStore = useFlashcardStore()

const config = ref({
  num_cards: 10,
  topic: '',
})

const error = ref('')

const selectedCount = computed(() => props.selectedDocs.length)

const isConfigValid = computed(() => {
  const total = config.value.num_cards
  return Number.isInteger(total) && total >= 1 && total <= 50
})

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      error.value = ''
      flashcardStore.loadHistory(20)
    }
  }
)

function handleClose() {
  emit('update:show', false)
  emit('close')
}

function handleGenerate() {
  error.value = ''
  if (props.selectedDocs.length === 0) {
    error.value = 'Please select at least one document'
    return
  }
  if (!isConfigValid.value) {
    error.value = 'Number of cards must be between 1 and 50'
    return
  }
  emit('generate', JSON.parse(JSON.stringify(config.value)))
}

function handleOpenHistory(deck) {
  flashcardStore.selectFromHistory(deck)
  emit('view')
}

async function handleDeleteHistory(deckId) {
  const ok = await flashcardStore.remove(deckId)
  if (!ok) {
    error.value = flashcardStore.error || 'Failed to delete flashcards'
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Flashcard Generator</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close flashcard modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="selected-docs-info">
            <div class="info-header">
              <span class="info-icon">📄</span>
              <span class="info-text">{{ selectedCount }} document(s) selected</span>
            </div>
            <div class="doc-list">
              <div v-for="doc in selectedDocs" :key="doc" class="doc-item">
                <span class="doc-icon">📋</span>
                <span class="doc-name" :title="doc">{{ doc }}</span>
              </div>
            </div>
          </div>

          <div class="config-section">
            <h4>Flashcard Configuration</h4>

            <div class="config-item">
              <label class="config-label">Number of Cards</label>
              <input
                type="number"
                min="1"
                max="50"
                class="num-input"
                v-model.number="config.num_cards"
              />
            </div>

            <div class="config-item">
              <label class="config-label">Focus Topic (optional)</label>
              <input
                type="text"
                class="topic-input"
                placeholder="e.g. sorting algorithms, cell biology..."
                v-model="config.topic"
              />
            </div>
          </div>

          <div class="history-section" v-if="flashcardStore.deckHistory.length > 0">
            <h4>Recent Decks</h4>
            <div v-if="flashcardStore.isLoading" class="history-empty">Loading...</div>
            <div v-for="deck in flashcardStore.deckHistory" :key="deck.id" class="history-item">
              <div class="history-info">
                <span class="history-docs">{{ deck.documents.join(', ') }}</span>
                <span class="history-meta">
                  {{ deck.card_count !== undefined ? `${deck.card_count} cards` : '' }}
                </span>
              </div>
              <div class="history-actions">
                <button type="button" class="btn-history" @click="handleOpenHistory(deck)">Open</button>
                <button type="button" class="btn-history danger" @click="handleDeleteHistory(deck.id)">Delete</button>
              </div>
            </div>
          </div>

          <div v-if="error || flashcardStore.error" class="error-message">
            {{ error || flashcardStore.error }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="handleClose">Cancel</button>
          <button
            class="btn-generate"
            @click="handleGenerate"
            :disabled="flashcardStore.isGenerating || selectedCount === 0 || !isConfigValid"
          >
            {{ flashcardStore.isGenerating ? 'Generating...' : '✨ Generate Flashcards' }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: min(600px, 90vw);
  max-height: 85vh;
  background: var(--surface-container);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--outline-variant);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--on-surface);
}

.modal-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.modal-close:hover {
  background: var(--tertiary-container);
  color: var(--on-tertiary);
  transform: rotate(90deg);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.selected-docs-info {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 12px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.info-icon {
  font-size: 16px;
}

.info-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-container);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--surface-container);
  font-size: 11px;
  color: var(--on-surface-variant);
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.config-section h4,
.history-section h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.config-item {
  margin-bottom: 16px;
}

.config-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 8px;
}

.num-input {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.topic-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.history-section {
  border-top: 1px solid var(--outline-variant);
  padding-top: 16px;
}

.history-empty {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--surface-container-high);
  margin-bottom: 6px;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.history-docs {
  font-size: 12px;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 10px;
  color: var(--on-surface-variant);
}

.history-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-history {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 11px;
  cursor: pointer;
}

.btn-history:hover {
  border-color: var(--primary);
}

.btn-history.danger:hover {
  border-color: #ef4444;
  color: #ef4444;
}

.error-message {
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--tertiary-container);
  border: 1px solid var(--tertiary);
  color: var(--on-tertiary);
  font-size: 12px;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  background: var(--surface-container-low);
}

.btn-cancel {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel:hover {
  border-color: var(--on-surface-variant);
}

.btn-generate {
  padding: 10px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  color: var(--on-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-generate:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 25px var(--primary);
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(20px);
}
</style>
