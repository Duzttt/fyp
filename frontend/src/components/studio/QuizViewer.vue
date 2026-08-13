<script setup>
import { reactive, computed } from 'vue'

const props = defineProps({
  quiz: {
    type: Object,
    default: null,
  },
  result: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close', 'submit', 'retake'])

const answers = reactive({})

const questions = computed(() => (props.quiz && props.quiz.questions) || [])

const allAnswered = computed(
  () =>
    questions.value.length > 0 &&
    questions.value.every((q) => !!answers[q.id])
)

const resultMap = computed(() => {
  const map = {}
  for (const r of props.result?.results || []) {
    map[r.question_id] = r
  }
  return map
})

const selectOption = (questionId, label) => {
  if (props.result || props.loading) return
  answers[questionId] = label
}

const handleSubmit = () => {
  if (!allAnswered.value || props.loading) return
  const payload = questions.value.map((q) => ({
    question_id: q.id,
    selected: answers[q.id],
  }))
  emit('submit', payload)
}

const handleRetake = () => {
  Object.keys(answers).forEach((key) => delete answers[key])
  emit('retake')
}

const optionClass = (questionId, label) => {
  if (!props.result) {
    return { selected: answers[questionId] === label }
  }
  const r = resultMap.value[questionId]
  if (label === r.correct_answer) return { correct: true }
  if (label === r.selected) return { incorrect: true }
  return {}
}
</script>

<template>
  <div v-if="quiz" class="quiz-viewer">
    <div v-if="result" class="score-card">
      <span class="score-title">Score</span>
      <span class="score-value">{{ result.score }} / {{ result.total }}</span>
      <span class="score-pct">{{ result.percentage }}%</span>
    </div>

    <div v-for="(q, index) in questions" :key="q.id" class="question-card">
      <div class="question-stem">
        <span class="question-num">{{ index + 1 }}.</span>
        <span>{{ q.question }}</span>
      </div>

      <div class="options-list">
        <button
          v-for="(text, label) in q.options"
          :key="label"
          type="button"
          class="option-row"
          :class="optionClass(q.id, label)"
          @click="selectOption(q.id, label)"
        >
          <span class="option-label">{{ label }}</span>
          <span class="option-text">{{ text }}</span>
        </button>
      </div>

      <div v-if="resultMap[q.id]" class="explanation-box">
        <span class="explanation-mark" :class="resultMap[q.id].is_correct ? 'ok' : 'bad'">
          {{ resultMap[q.id].is_correct ? 'Correct' : 'Incorrect' }}
        </span>
        <span class="explanation-text">{{ resultMap[q.id].explanation }}</span>
      </div>
    </div>

    <div class="quiz-footer">
      <button
        v-if="!result"
        type="button"
        class="btn-submit"
        :disabled="!allAnswered || loading"
        @click="handleSubmit"
      >
        {{ loading ? 'Submitting...' : 'Submit Answers' }}
      </button>
      <button v-else type="button" class="btn-retake" @click="handleRetake">
        Retake Quiz
      </button>
    </div>
  </div>
</template>

<style scoped>
.quiz-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-card {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
}

.score-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--on-surface-variant);
}

.score-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--on-surface);
}

.score-pct {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-container);
}

.question-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface-container);
  border: 1px solid var(--outline-variant);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-stem {
  display: flex;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
  line-height: 1.5;
}

.question-num {
  color: var(--primary-container);
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}

.option-row:hover:not(.correct):not(.incorrect) {
  border-color: var(--primary);
}

.option-label {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.option-row.selected {
  border-color: var(--primary-container);
  background: var(--primary-container);
}

.option-row.correct {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

.option-row.correct .option-label {
  border-color: #22c55e;
  color: #22c55e;
}

.option-row.incorrect {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.12);
}

.option-row.incorrect .option-label {
  border-color: #ef4444;
  color: #ef4444;
}

.explanation-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-radius: 10px;
  background: var(--surface-container-high);
}

.explanation-mark {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.explanation-mark.ok {
  color: #22c55e;
}

.explanation-mark.bad {
  color: #ef4444;
}

.explanation-text {
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

.quiz-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-submit,
.btn-retake {
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

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
