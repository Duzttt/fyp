<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import { useQuizStore } from '../../stores/quizStore'
import { useFlashcardStore } from '../../stores/flashcardStore'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'
import QuizModal from '../studio/QuizModal.vue'
import QuizSessionViewer from '../studio/QuizSessionViewer.vue'
import FlashcardModal from '../studio/FlashcardModal.vue'
import FlashcardSessionViewer from '../studio/FlashcardSessionViewer.vue'

const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()
const quizStore = useQuizStore()
const flashcardStore = useFlashcardStore()

const studioTools = [
  {
    id: 'summary',
    title: 'Summarize PDF',
    desc: 'Condense complex papers into high-level editorial abstracts.',
    icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z',
    action: 'summary',
  },
  {
    id: 'quiz',
    title: 'Quiz',
    desc: 'Test your understanding with an interactive quiz.',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z',
    action: 'quiz',
  },
  {
    id: 'flashcard',
    title: 'Flashcards',
    desc: 'Review key concepts with flip-style flashcards.',
    icon: 'M2.53 19.65l1.34.56v-9.03l-2.43 5.86c-.41 1.02.06 2.19 1.09 2.49zm19.5-3.7L17.07 3.98c-.31-.81-1.18-1.23-1.97-.91L2.96 7.58c-.81.31-1.23 1.18-.91 1.97l5.12 13.01c.31.81 1.18 1.23 1.97.91l12.87-4.87c.81-.31 1.24-1.17.92-1.97zM7.88 8.75c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-2 11c0 1.1.9 2 2 2h1.45l-3.45-8.77v6.77zm6 1.5c0 1.1.9 2 2 2h1.55l-3.55-9.02v7.02z',
    action: 'flashcard',
  },
  {
    id: 'datatable',
    title: 'Data Table',
    desc: 'Extract structured data tables from your documents.',
    icon: 'M20 3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM8 19H4v-6h4v6zm0-8H4V5h4v6zm6 8h-4v-6h4v6zm0-8h-4V5h4v6zm6 8h-4v-6h4v6zm0-8h-4V5h4v6z',
    comingSoon: true,
  },
]

const showSummaryModal = ref(false)
const showSummaryViewer = ref(false)
const showQuizModal = ref(false)
const showQuizSessionViewer = ref(false)
const showFlashcardModal = ref(false)
const showFlashcardSessionViewer = ref(false)

const selectedDocs = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => selectedDocs.value.length)

const handleToolClick = (tool) => {
  if (tool.disabled) return
  if (tool.comingSoon) {
    alert(`${tool.title} is coming soon`)
    return
  }
  if (tool.action === 'summary') {
    openSummaryModal()
  }
  if (tool.action === 'quiz') {
    openQuizModal()
  }
  if (tool.action === 'flashcard') {
    openFlashcardModal()
  }
}

const openSummaryModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showSummaryModal.value = true
}

const openQuizModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showQuizModal.value = true
}

const openFlashcardModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showFlashcardModal.value = true
}

const handleFlashcardGenerate = async (config) => {
  const deck = await flashcardStore.generate(selectedDocs.value, config)
  if (deck) {
    showFlashcardModal.value = false
    showFlashcardSessionViewer.value = true
  }
}

const handleFlashcardOpenFromHistory = () => {
  showFlashcardModal.value = false
  showFlashcardSessionViewer.value = true
}

const closeFlashcardSessionViewer = () => {
  showFlashcardSessionViewer.value = false
  flashcardStore.clearCurrent()
}

const handleQuizGenerate = async (config) => {
  const quiz = await quizStore.generate(selectedDocs.value, config)
  if (quiz) {
    showQuizModal.value = false
    showQuizSessionViewer.value = true
  }
}

const handleQuizOpenFromHistory = () => {
  showQuizModal.value = false
  showQuizSessionViewer.value = true
}

const closeQuizSessionViewer = () => {
  showQuizSessionViewer.value = false
  quizStore.clearCurrent()
}

const handleSummaryCreated = () => {
  showSummaryModal.value = false
  showSummaryViewer.value = true
}

const closeSummaryViewer = () => {
  showSummaryViewer.value = false
  summaryStore.reset()
}
</script>

<template>
  <div class="panel studio-panel">
    <div class="panel-header">
      <h2 class="panel-title">Studio Tools</h2>
    </div>

    <div class="panel-body">
      <div class="tools-list">
        <button
          v-for="tool in studioTools"
          :key="tool.id"
          type="button"
          class="tool-card"
          :class="{ disabled: tool.disabled }"
          :disabled="tool.disabled"
          @click="handleToolClick(tool)"
        >
          <div class="tool-icon-wrap">
            <svg class="tool-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="tool.icon" /></svg>
          </div>
          <div class="tool-content">
            <span class="tool-title">{{ tool.title }}</span>
            <span class="tool-desc">{{ tool.desc }}</span>
          </div>
          <span v-if="tool.comingSoon" class="tool-badge soon" aria-hidden="true">Soon</span>
          <span v-else-if="['summary', 'quiz', 'flashcard'].includes(tool.action) && selectedCount > 0" class="tool-badge" aria-hidden="true">
            {{ selectedCount }}
          </span>
        </button>
      </div>

      <Teleport to="body">
        <Transition name="modal-fade">
          <div v-if="showSummaryViewer" class="summary-modal-overlay" @click.self="closeSummaryViewer">
            <div class="summary-modal">
              <div class="modal-header">
                <span class="modal-title">Summary</span>
                <button type="button" class="modal-close" aria-label="Close summary" @click="closeSummaryViewer">
                  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
              </div>
              <div class="modal-body">
                <SummaryViewer
                  :show="showSummaryViewer"
                  @close="closeSummaryViewer"
                />
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <Teleport to="body">
        <Transition name="modal-fade">
          <div v-if="showQuizSessionViewer" class="summary-modal-overlay" @click.self="closeQuizSessionViewer">
            <div class="summary-modal">
              <div class="modal-header">
                <span class="modal-title">Quiz</span>
                <button type="button" class="modal-close" aria-label="Close quiz" @click="closeQuizSessionViewer">
                  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
              </div>
              <div class="modal-body">
                <QuizSessionViewer
                  v-model:show="showQuizSessionViewer"
                  @close="closeQuizSessionViewer"
                />
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <Teleport to="body">
        <Transition name="modal-fade">
          <div v-if="showFlashcardSessionViewer" class="summary-modal-overlay" @click.self="closeFlashcardSessionViewer">
            <div class="summary-modal">
              <div class="modal-header">
                <span class="modal-title">Flashcards</span>
                <button type="button" class="modal-close" aria-label="Close flashcards" @click="closeFlashcardSessionViewer">
                  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
              </div>
              <div class="modal-body">
                <FlashcardSessionViewer
                  v-model:show="showFlashcardSessionViewer"
                  @close="closeFlashcardSessionViewer"
                />
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

    </div>

    <SummaryModal
      v-model:show="showSummaryModal"
      :selected-docs="selectedDocs"
      @created="handleSummaryCreated"
      @close="showSummaryModal = false"
    />

    <QuizModal
      v-model:show="showQuizModal"
      :selected-docs="selectedDocs"
      @generate="handleQuizGenerate"
      @view="handleQuizOpenFromHistory"
      @close="showQuizModal = false"
    />

    <FlashcardModal
      v-model:show="showFlashcardModal"
      :selected-docs="selectedDocs"
      @generate="handleFlashcardGenerate"
      @view="handleFlashcardOpenFromHistory"
      @close="showFlashcardModal = false"
    />
  </div>
</template>

<style scoped>
.studio-panel {
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  padding: 16px 16px 12px;
}

.panel-title {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface-variant);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.panel-body {
  flex: 1;
  padding: 0 12px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 10px;
  border: none;
  width: 100%;
  text-align: left;
  background: var(--surface-container);
  cursor: pointer;
  transition: background-color 0.2s;
  position: relative;
  font: inherit;
  color: inherit;
}

.tool-card:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.tool-card:disabled {
  cursor: not-allowed;
}

.tool-card:hover:not(.disabled) {
  background: var(--surface-container-high);
}

.tool-card.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tool-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(129, 140, 248, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

.tool-card.disabled .tool-icon-wrap {
  background: rgba(69, 70, 83, 0.15);
}

.tool-card.disabled .tool-icon {
  color: var(--on-surface-variant);
}

.tool-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.tool-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
}

.tool-desc {
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.4;
}

.tool-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  background: var(--primary-container);
  color: var(--on-primary);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}

.tool-badge.soon {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.summary-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-message {
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--tertiary-container);
  border: 1px solid var(--tertiary);
  color: var(--on-tertiary);
  font-size: 12px;
}

.summary-modal {
  width: 90vw;
  max-width: 720px;
  max-height: 85vh;
  background: var(--surface-container);
  border-radius: 16px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(129, 140, 248, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-title {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 600;
  color: var(--primary);
}

.modal-close {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s, color 0.2s;
}

.modal-close:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.modal-close svg {
  width: 18px;
  height: 18px;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--on-surface);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-active .summary-modal,
.modal-fade-leave-active .summary-modal {
  transition: transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .summary-modal {
  transform: scale(0.95);
}

.modal-fade-leave-to .summary-modal {
  transform: scale(0.95);
}

</style>
