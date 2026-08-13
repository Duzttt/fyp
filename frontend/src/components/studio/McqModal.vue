<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:show', 'close', 'generate'])

const config = ref({
  num_questions: 5,
  difficulty: 'mixed',
})

const error = ref('')

const selectedCount = computed(() => props.selectedDocs.length)

const countOptions = [
  { value: 5, label: '5 questions', desc: 'Quick check' },
  { value: 10, label: '10 questions', desc: 'Standard quiz' },
  { value: 15, label: '15 questions', desc: 'Thorough review' },
]

const difficultyOptions = [
  { value: 'mixed', label: 'Mixed', desc: 'Easy, medium, and hard mix' },
  { value: 'easy', label: 'Easy', desc: 'Recall of facts and definitions' },
  { value: 'medium', label: 'Medium', desc: 'Understanding concepts' },
  { value: 'hard', label: 'Hard', desc: 'Analysis and application' },
]

const handleClose = () => {
  emit('update:show', false)
  emit('close')
  error.value = ''
}

const handleGenerate = () => {
  if (selectedCount.value === 0) {
    error.value = 'Please select at least one document'
    return
  }
  error.value = ''
  emit('generate', { ...config.value })
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Generate MCQ</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close MCQ modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="selected-docs-info">
            <span class="info-text">{{ selectedCount }} document(s) selected</span>
          </div>

          <div class="config-section">
            <h4>Quiz Configuration</h4>

            <div class="config-item">
              <label class="config-label">Number of Questions</label>
              <div class="option-grid">
                <button
                  v-for="opt in countOptions"
                  :key="opt.value"
                  class="option-card"
                  :class="{ active: config.num_questions === opt.value }"
                  @click="config.num_questions = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>

            <div class="config-item">
              <label class="config-label">Difficulty</label>
              <div class="option-grid">
                <button
                  v-for="opt in difficultyOptions"
                  :key="opt.value"
                  class="option-card"
                  :class="{ active: config.difficulty === opt.value }"
                  @click="config.difficulty = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="error" class="error-message">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="handleClose" :disabled="loading">
            Cancel
          </button>
          <button
            class="btn-generate"
            @click="handleGenerate"
            :disabled="loading || selectedCount === 0"
          >
            {{ loading ? 'Generating...' : '✨ Generate Quiz' }}
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

.info-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-container);
}

.config-section h4 {
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

.option-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
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

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
