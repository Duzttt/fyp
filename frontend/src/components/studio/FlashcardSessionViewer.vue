<script setup>
import { ref, computed, watch } from 'vue'
import { useFlashcardStore } from '../../stores/flashcardStore'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show', 'close'])

const flashcardStore = useFlashcardStore()

const mode = ref('browse') // 'browse' | 'quiz'
const currentIndex = ref(0)
const flipped = ref(false)
const showHint = ref(false)
const quizRatings = ref({}) // index -> 'again' | 'got'
const quizDone = ref(false)

const deck = computed(() => flashcardStore.currentDeck)
const cards = computed(() => deck.value?.cards || [])

const currentCard = computed(() => cards.value[currentIndex.value] || null)
const total = computed(() => cards.value.length)

const ratedCount = computed(() => Object.keys(quizRatings.value).length)
const againIndices = computed(() =>
  Object.entries(quizRatings.value)
    .filter(([, rating]) => rating === 'again')
    .map(([index]) => Number(index))
)

watch(
  () => props.show,
  (visible) => {
    if (visible) resetSession()
  },
  { immediate: true }
)

function resetSession() {
  mode.value = 'browse'
  currentIndex.value = 0
  flipped.value = false
  showHint.value = false
  quizRatings.value = {}
  quizDone.value = false
}

function goPrev() {
  if (currentIndex.value > 0) {
    currentIndex.value--
    flipped.value = false
    showHint.value = false
  }
}

function goNext() {
  if (currentIndex.value < total.value - 1) {
    currentIndex.value++
    flipped.value = false
    showHint.value = false
  }
}

function flipCard() {
  flipped.value = !flipped.value
}

function startQuiz() {
  mode.value = 'quiz'
  currentIndex.value = 0
  flipped.value = false
  showHint.value = false
  quizRatings.value = {}
  quizDone.value = false
}

function rateQuiz(rating) {
  if (!currentCard.value) return
  quizRatings.value[currentIndex.value] = rating
  showHint.value = false
  flipped.value = false

  if (ratedCount.value >= total.value) {
    quizDone.value = true
    return
  }

  const next = currentIndex.value + 1
  if (next < total.value) {
    currentIndex.value = next
  }
}

function redoAgain() {
  mode.value = 'quiz'
  currentIndex.value = 0
  flipped.value = false
  showHint.value = false
  quizRatings.value = {}
  quizDone.value = false
  deck.value.cards = againIndices.value.map((index) => cards.value[index])
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
          <h3>Flashcards</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close flashcards">✕</button>
        </div>

        <div class="modal-body" v-if="deck">
          <div v-if="total === 0" class="empty-state">
            No flashcards to review.
          </div>

          <template v-else>
            <div class="mode-toggle">
              <button
                type="button"
                class="mode-btn"
                :class="{ active: mode === 'browse' }"
                @click="mode = 'browse'; flipped = false; showHint = false"
              >
                Browse
              </button>
              <button
                type="button"
                class="mode-btn"
                :class="{ active: mode === 'quiz' }"
                @click="startQuiz"
              >
                Quiz
              </button>
            </div>

            <div class="progress-row" v-if="mode === 'browse' || !quizDone">
              <span>Card {{ currentIndex + 1 }} of {{ total }}</span>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: `${((currentIndex + 1) / total) * 100}%` }"></div>
              </div>
              <span v-if="mode === 'quiz'" class="rated-note">{{ ratedCount }} / {{ total }} rated</span>
            </div>

            <div v-if="quizDone" class="score-panel">
              <div class="score-label">Session complete</div>
              <div class="score-line">{{ total - againIndices.length }} remembered · {{ againIndices.length }} to review</div>
            </div>

            <div v-else-if="currentCard" class="flashcard-wrap">
              <div class="flashcard" :class="{ flipped }" @click="flipCard">
                <div class="flashcard-face front">
                  <span class="face-label">FRONT</span>
                  <span class="face-text">{{ currentCard.front }}</span>
                  <span v-if="currentCard.tags && currentCard.tags.length" class="tags">
                    <span v-for="tag in currentCard.tags" :key="tag" class="tag">{{ tag }}</span>
                  </span>
                  <span v-if="currentCard.hint && showHint" class="hint hint-front">Hint: {{ currentCard.hint }}</span>
                </div>
                <div class="flashcard-face back">
                  <span class="face-label">BACK</span>
                  <span class="face-text">{{ currentCard.back }}</span>
                </div>
              </div>
              <p class="flip-hint">Click the card to flip it</p>
            </div>

            <div v-if="mode === 'browse' && !quizDone" class="nav-row">
              <button class="nav-btn" @click="goPrev" :disabled="currentIndex === 0">← Previous</button>
              <button
                v-if="currentCard && currentCard.hint"
                class="nav-btn hint-btn"
                @click="showHint = !showHint"
              >
                {{ showHint ? 'Hide Hint' : 'Show Hint' }}
              </button>
              <button class="nav-btn" @click="goNext" :disabled="currentIndex === total - 1">Next →</button>
            </div>

            <div v-else-if="mode === 'quiz' && !quizDone" class="quiz-rate-row">
              <button
                v-if="currentCard && currentCard.hint"
                class="nav-btn hint-btn"
                @click="showHint = !showHint"
              >
                {{ showHint ? 'Hide Hint' : 'Show Hint' }}
              </button>
              <button class="rate-btn again" @click="rateQuiz('again')">Again</button>
              <button class="rate-btn got" @click="rateQuiz('got')">Got it</button>
            </div>
          </template>
        </div>

        <div class="modal-footer" v-if="deck && total > 0">
          <span class="footer-note">{{ deck.documents.join(', ') }}</span>
          <div class="footer-actions">
            <button
              v-if="quizDone && againIndices.length > 0"
              class="btn-retake"
              @click="redoAgain"
            >
              Review Again Cards ({{ againIndices.length }})
            </button>
            <button class="btn-cancel" @click="handleClose">Close</button>
          </div>
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
  perspective: 1200px;
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

.empty-state {
  text-align: center;
  padding: 40px 0;
  font-size: 13px;
  color: var(--on-surface-variant);
}

.mode-toggle {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.mode-btn {
  padding: 8px 22px;
  border-radius: 20px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: var(--primary-container);
  color: var(--on-primary);
  border-color: var(--primary-container);
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.progress-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--primary-container), var(--primary));
  transition: width 0.25s;
}

.rated-note {
  white-space: nowrap;
}

.flashcard-wrap {
  perspective: 1200px;
}

.flashcard {
  position: relative;
  width: 100%;
  height: 300px;
  cursor: pointer;
  transform-style: preserve-3d;
  transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.flashcard.flipped {
  transform: rotateY(180deg);
}

.flashcard-face {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  text-align: center;
}

.flashcard-face.back {
  background: var(--primary-container);
  border-color: var(--primary-container);
  transform: rotateY(180deg);
}

.face-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-surface-variant);
}

.flashcard-face.back .face-label {
  color: var(--on-primary);
  opacity: 0.8;
}

.face-text {
  font-size: 20px;
  font-weight: 600;
  color: var(--on-surface);
  line-height: 1.4;
  max-width: 460px;
}

.flashcard-face.back .face-text {
  color: var(--on-primary);
  font-size: 17px;
  font-weight: 500;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 4px;
}

.tag {
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 10px;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.hint {
  font-size: 12px;
  color: var(--on-surface-variant);
  font-style: italic;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(129, 140, 248, 0.12);
  border: 1px dashed var(--primary-container);
  max-width: 420px;
  text-align: center;
}

.flip-hint {
  margin: 10px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--on-surface-variant);
}

.nav-row,
.quiz-rate-row {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.nav-btn {
  padding: 9px 18px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  border-color: var(--primary);
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-btn.hint-btn {
  color: var(--primary);
  border-color: var(--primary-container);
}

.rate-btn {
  padding: 10px 26px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.rate-btn.again {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.rate-btn.again:hover {
  background: rgba(239, 68, 68, 0.25);
}

.rate-btn.got {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.rate-btn.got:hover {
  background: rgba(34, 197, 94, 0.25);
}

.score-panel {
  text-align: center;
  padding: 24px;
  border-radius: 12px;
  background: var(--primary-container);
}

.score-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-primary);
  opacity: 0.9;
}

.score-line {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--on-primary);
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--surface-container-low);
}

.footer-note {
  font-size: 12px;
  color: var(--on-surface-variant);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.footer-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
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
