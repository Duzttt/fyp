<script setup>
import { ref, computed } from 'vue'
import { useSummaryStore } from '../../stores/summaryStore'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'close', 'created'])

const summaryStore = useSummaryStore()

const length = ref('medium')
const error = ref('')
const isSubmitting = ref(false)

const selectedCount = computed(() => props.selectedDocs.length)
const firstDoc = computed(() => (props.selectedDocs.length ? props.selectedDocs[0] : ''))

const lengthOptions = [
  { value: 'short', label: 'Short', desc: 'About 4 topics' },
  { value: 'medium', label: 'Medium', desc: 'About 8 topics' },
  { value: 'detailed', label: 'Detailed', desc: 'About 12 topics' },
]

const handleClose = () => {
  emit('update:show', false)
  emit('close')
  error.value = ''
}

const handleGenerate = async () => {
  if (!firstDoc.value) {
    error.value = 'Please select a document'
    return
  }
  isSubmitting.value = true
  error.value = ''
  try {
    const job = await summaryStore.createJob(firstDoc.value, { length: length.value })
    if (job) {
      emit('created')
    } else {
      error.value = summaryStore.error || 'Failed to start summary'
    }
  } catch (err) {
    error.value = err?.message || 'Failed to start summary'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Summarize PDF</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close summary modal">✕</button>
        </div>
        <div class="modal-body">
          <div class="selected-docs-info">
            <div class="info-header">
              <span class="info-icon">📄</span>
              <span class="info-text">{{ selectedCount }} document(s) selected</span>
            </div>
            <div class="doc-list">
              <div class="doc-item">
                <span class="doc-icon">📋</span>
                <span class="doc-name" :title="firstDoc">{{ firstDoc || 'No document selected' }}</span>
              </div>
            </div>
            <p class="doc-note">
              <strong>Summary target:</strong> {{ firstDoc || 'No document selected' }}
              {{ selectedCount > 1 ? ' — only the first selected document is summarized.' : '' }}
            </p>
          </div>

          <div class="config-section">
            <h4>Summary Length</h4>
            <div class="config-item">
              <label class="config-label">Detail level (number of topics)</label>
              <div class="option-grid">
                <button
                  v-for="opt in lengthOptions"
                  :key="opt.value"
                  class="option-card"
                  :class="{ active: length === opt.value }"
                  @click="length = opt.value"
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
          <button class="btn-cancel" @click="handleClose" :disabled="isSubmitting">
            Cancel
          </button>
          <button
            class="btn-generate"
            @click="handleGenerate"
            :disabled="isSubmitting || selectedCount === 0"
          >
            {{ isSubmitting ? 'Starting...' : 'Generate Summary' }}
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
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: min(520px, 90vw);
  max-height: 85vh;
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

.info-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-container);
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

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-note {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--on-surface-variant);
}

.config-section h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.06em;
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
}
</style>
