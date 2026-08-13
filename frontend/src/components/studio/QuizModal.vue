<script setup>
import { ref, computed, watch } from 'vue'
import { useQuizStore } from '../../stores/quizStore'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'close', 'generate', 'view'])

const quizStore = useQuizStore()

const config = ref({
  num_questions: 5,
  difficulty: 'medium',
  question_types: { single: 3, multiple: 2 },
})

const error = ref('')

const selectedCount = computed(() => props.selectedDocs.length)

const typeSum = computed(
  () => config.value.question_types.single + config.value.question_types.multiple
)

const isConfigValid = computed(() => {
  const total = config.value.num_questions
  if (!Number.isInteger(total) || total < 1 || total > 20) return false
  if (config.value.question_types.single < 0 || config.value.question_types.multiple < 0) {
    return false
  }
  return typeSum.value === total
})

const difficultyOptions = [
  { value: 'easy', label: 'Easy', desc: 'Basic recall of facts and definitions' },
  { value: 'medium', label: 'Medium', desc: 'Understanding and application' },
  { value: 'hard', label: 'Hard', desc: 'Analysis and synthesis' },
]

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      error.value = ''
      quizStore.loadHistory(20)
    }
  }
)

function onTotalChange() {
  const total = config.value.num_questions || 1
  const single = Math.max(0, Math.round(total * 0.6))
  config.value.question_types = { single, multiple: total - single }
}

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
    error.value = 'Single + multiple must equal the total number of questions'
    return
  }
  emit('generate', JSON.parse(JSON.stringify(config.value)))
}

function handleOpenHistory(quiz) {
  quizStore.selectFromHistory(quiz)
  emit('view')
}

async function handleDeleteHistory(quizId) {
  const ok = await quizStore.remove(quizId)
  if (!ok) {
    error.value = quizStore.error || 'Failed to delete quiz'
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Quiz Generator</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close quiz modal">✕</button>
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
            <h4>Quiz Configuration</h4>

            <div class="config-item">
              <label class="config-label">Number of Questions</label>
              <input
                type="number"
                min="1"
                max="20"
                class="num-input"
                v-model.number="config.num_questions"
                @change="onTotalChange"
              />
            </div>

            <div class="config-item">
              <label class="config-label">Difficulty</label>
              <div class="option-grid">
                <button
                  v-for="opt in difficultyOptions"
                  :key="opt.value"
                  type="button"
                  class="option-card"
                  :class="{ active: config.difficulty === opt.value }"
                  @click="config.difficulty = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>

            <div class="config-item">
              <label class="config-label">Question Types</label>
              <div class="type-row">
                <div class="type-input">
                  <span class="type-name">Single choice</span>
                  <input
                    type="number"
                    min="0"
                    class="type-num"
                    v-model.number="config.question_types.single"
                  />
                </div>
                <div class="type-input">
                  <span class="type-name">Multiple choice</span>
                  <input
                    type="number"
                    min="0"
                    class="type-num"
                    v-model.number="config.question_types.multiple"
                  />
                </div>
              </div>
              <p v-if="!isConfigValid" class="type-warning">
                Single + multiple must equal {{ config.num_questions }}
              </p>
            </div>
          </div>

          <div class="history-section" v-if="quizStore.quizHistory.length > 0">
            <h4>Recent Quizzes</h4>
            <div v-if="quizStore.isLoading" class="history-empty">Loading...</div>
            <div v-for="quiz in quizStore.quizHistory" :key="quiz.id" class="history-item">
              <div class="history-info">
                <span class="history-docs">{{ quiz.documents.join(', ') }}</span>
                <span class="history-meta">
                  {{ quiz.config ? `${quiz.config.num_questions} questions` : '' }}
                </span>
              </div>
              <div class="history-actions">
                <button type="button" class="btn-history" @click="handleOpenHistory(quiz)">Open</button>
                <button type="button" class="btn-history danger" @click="handleDeleteHistory(quiz.id)">Delete</button>
              </div>
            </div>
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="handleClose">Cancel</button>
          <button
            class="btn-generate"
            @click="handleGenerate"
            :disabled="quizStore.isGenerating || selectedCount === 0 || !isConfigValid"
          >
            {{ quizStore.isGenerating ? 'Generating...' : '✨ Generate Quiz' }}
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

.num-input,
.type-num {
  width: 100px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.option-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}

.option-card:hover {
  border-color: var(--primary);
  background: var(--surface-container-high);
}

.option-card.active {
  border-color: var(--primary-container);
  background: var(--primary-container);
  box-shadow: 0 0 0 1px var(--primary);
}

.option-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
}

.option-desc {
  font-size: 10px;
  color: var(--on-surface-variant);
}

.type-row {
  display: flex;
  gap: 24px;
}

.type-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.type-name {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.type-warning {
  margin: 8px 0 0;
  font-size: 11px;
  color: #fbbf24;
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
