<script setup>
import { ref, computed, watch } from 'vue'
import { useQuizStore } from '../../stores/quizStore'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show', 'close'])

const quizStore = useQuizStore()

const phase = ref('answering')
const activeIndices = ref([])
const answers = ref({})
const submitError = ref('')

const quiz = computed(() => quizStore.currentQuiz)
const isSubmitting = computed(() => quizStore.isSubmitting)
const result = computed(() => quizStore.lastResult)

const activeQuestions = computed(() => {
  if (!quiz.value) return []
  return activeIndices.value
    .map((index) => ({ index, question: quiz.value.questions[index] }))
    .filter((item) => item.question)
})

const answeredCount = computed(() => {
  return activeQuestions.value.filter((item) => {
    const answer = answers.value[item.index]
    return Array.isArray(answer) && answer.length > 0
  }).length
})

const wrongIndices = computed(() => {
  if (!result.value) return []
  return result.value.per_question
    .filter((item) => !item.correct)
    .map((item) => item.index)
})

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      resetSession()
    }
  }
)

function resetSession() {
  phase.value = 'answering'
  submitError.value = ''
  answers.value = {}
  activeIndices.value = quiz.value
    ? quiz.value.questions.map((_, index) => index)
    : []
}

function toggleOption(questionIndex, optionIndex) {
  const question = quiz.value?.questions[questionIndex]
  if (!question) return

  if (question.type === 'single') {
    answers.value[questionIndex] = [optionIndex]
    return
  }

  if (!answers.value[questionIndex]) {
    answers.value[questionIndex] = []
  }
  const current = answers.value[questionIndex]
  const position = current.indexOf(optionIndex)
  if (position === -1) {
    current.push(optionIndex)
  } else {
    current.splice(position, 1)
  }
}

function resultFor(index) {
  if (!result.value) return null
  return result.value.per_question.find((item) => item.index === index) || null
}

async function handleSubmit() {
  submitError.value = ''
  const unanswered = activeQuestions.value.filter((item) => {
    const answer = answers.value[item.index]
    return !(Array.isArray(answer) && answer.length > 0)
  })

  if (unanswered.length > 0) {
    submitError.value = `Please answer all questions (${unanswered.length} unanswered)`
    return
  }

  const payload = {}
  for (const item of activeQuestions.value) {
    payload[item.index] = answers.value[item.index]
  }

  const submission = await quizStore.submit(payload)
  if (submission) {
    phase.value = 'results'
  } else {
    submitError.value = quizStore.error || 'Failed to submit quiz'
  }
}

function startRetake() {
  activeIndices.value = [...wrongIndices.value]
  answers.value = {}
  phase.value = 'answering'
  submitError.value = ''
}

function handleClose() {
  emit('update:show', false)
  emit('close')
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Quiz</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close quiz">✕</button>
        </div>

        <div class="modal-body" v-if="quiz">
          <div class="quiz-meta" v-if="phase === 'answering'">
            <span>{{ answeredCount }} / {{ activeQuestions.length }} answered</span>
            <span class="quiz-docs">{{ quiz.documents.join(', ') }}</span>
          </div>

          <template v-if="phase === 'answering'">
            <div v-for="item in activeQuestions" :key="item.index" class="question-card">
              <div class="question-header">
                <span class="question-number">Q{{ item.index + 1 }}</span>
                <span v-if="item.question.type === 'multiple'" class="type-badge">Multiple</span>
              </div>
              <p class="question-text">{{ item.question.text }}</p>
              <div class="options-list">
                <label
                  v-for="(option, optionIndex) in item.question.options"
                  :key="optionIndex"
                  class="option-item"
                  :class="{ selected: (answers[item.index] || []).includes(optionIndex) }"
                >
                  <input
                    :type="item.question.type === 'single' ? 'radio' : 'checkbox'"
                    :name="'question-' + item.index"
                    :checked="(answers[item.index] || []).includes(optionIndex)"
                    @change="toggleOption(item.index, optionIndex)"
                  />
                  <span class="option-letter">{{ String.fromCharCode(65 + optionIndex) }}</span>
                  <span class="option-text">{{ option }}</span>
                </label>
              </div>
            </div>

            <div v-if="submitError" class="error-message">{{ submitError }}</div>
          </template>

          <template v-else-if="phase === 'results' && result">
            <div class="score-panel">
              <div class="score-number">{{ result.score }} / {{ result.total }}</div>
              <div class="score-label">
                {{ result.score === result.total ? 'Perfect!' : result.score >= result.total / 2 ? 'Good effort!' : 'Keep reviewing!' }}
              </div>
            </div>

            <div
              v-for="item in activeQuestions"
              :key="item.index"
              class="question-card result-card"
            >
              <div class="question-header">
                <span class="question-number">Q{{ item.index + 1 }}</span>
                <span
                  class="result-badge"
                  :class="resultFor(item.index)?.correct ? 'correct' : 'wrong'"
                >
                  {{ resultFor(item.index)?.correct ? 'Correct' : 'Wrong' }}
                </span>
              </div>
              <p class="question-text">{{ item.question.text }}</p>
              <div class="options-list">
                <div
                  v-for="(option, optionIndex) in item.question.options"
                  :key="optionIndex"
                  class="option-item static"
                  :class="{
                    correct: (resultFor(item.index)?.correct_answers || []).includes(optionIndex),
                    wrong: (resultFor(item.index)?.your_answers || []).includes(optionIndex) && !(resultFor(item.index)?.correct_answers || []).includes(optionIndex),
                  }"
                >
                  <span class="option-letter">{{ String.fromCharCode(65 + optionIndex) }}</span>
                  <span class="option-text">{{ option }}</span>
                </div>
              </div>
              <div class="explanation">
                <strong>Explanation:</strong> {{ resultFor(item.index)?.explanation }}
              </div>
            </div>
          </template>
        </div>

        <div class="modal-footer" v-if="quiz">
          <template v-if="phase === 'answering'">
            <span class="footer-note">{{ activeQuestions.length }} question(s)</span>
            <div class="footer-actions">
              <button class="btn-cancel" @click="handleClose" :disabled="isSubmitting">Cancel</button>
              <button class="btn-generate" @click="handleSubmit" :disabled="isSubmitting">
                {{ isSubmitting ? 'Submitting...' : 'Submit Answers' }}
              </button>
            </div>
          </template>
          <template v-else-if="phase === 'results'">
            <span class="footer-note">Score: {{ result.score }} / {{ result.total }}</span>
            <div class="footer-actions">
              <button
                v-if="wrongIndices.length > 0"
                class="btn-retake"
                @click="startRetake"
              >
                Redo Wrong Questions ({{ wrongIndices.length }})
              </button>
              <button class="btn-cancel" @click="handleClose">Close</button>
            </div>
          </template>
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
  width: min(640px, 92vw);
  max-height: 88vh;
  background: var(--surface-container);
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
  gap: 16px;
}

.quiz-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.quiz-docs {
  max-width: 55%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.question-card {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 16px;
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.question-number {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-container);
}

.type-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.question-text {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--on-surface);
  line-height: 1.5;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  cursor: pointer;
  transition: all 0.15s;
}

.option-item:hover {
  border-color: var(--primary);
}

.option-item.selected {
  border-color: var(--primary-container);
  background: var(--primary-container);
}

.option-item input {
  width: 16px;
  height: 16px;
  accent-color: var(--primary-container);
  cursor: pointer;
  flex-shrink: 0;
}

.option-letter {
  font-size: 12px;
  font-weight: 700;
  color: var(--on-surface-variant);
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-text {
  font-size: 13px;
  color: var(--on-surface);
}

.option-item.static {
  cursor: default;
}

.option-item.static.correct {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

.option-item.static.wrong {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
}

.score-panel {
  text-align: center;
  padding: 20px;
  border-radius: 12px;
  background: var(--primary-container);
}

.score-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--on-primary);
}

.score-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--on-primary);
  opacity: 0.9;
}

.result-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 8px;
}

.result-badge.correct {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.result-badge.wrong {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.explanation {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--surface-container);
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.5;
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
  justify-content: space-between;
  background: var(--surface-container-low);
}

.footer-note {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.footer-actions {
  display: flex;
  gap: 10px;
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

.btn-cancel:hover:not(:disabled) {
  border-color: var(--on-surface-variant);
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

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-retake {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid var(--primary-container);
  background: var(--surface-container);
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-retake:hover {
  background: var(--primary-container);
  color: var(--on-primary);
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
