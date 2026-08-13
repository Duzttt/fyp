<script setup>
import { ref, computed, watch } from 'vue'
import { useSummaryStore } from '../../stores/summaryStore'
import PdfViewer from '../documents/PdfViewer.vue'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['close'])

const summaryStore = useSummaryStore()

const activeTab = ref('result')
const showPdf = ref(false)
const pdfState = ref({ url: '', page: 1, highlight: '' })

const job = computed(() => summaryStore.job)
const partialSections = computed(() => summaryStore.partialSections)
const history = computed(() => summaryStore.history)
const isActive = computed(
  () => job.value && ['queued', 'running'].includes(job.value.status)
)

const resultSections = computed(() => {
  if (job.value?.result_json?.sections) return job.value.result_json.sections
  return partialSections.value
})

const stageLabel = computed(() => {
  const labels = {
    language: 'Detecting language',
    topics: 'Discovering topics',
    partial: 'Summarizing topics',
    overview: 'Writing overview',
    render: 'Rendering notes',
    done: 'Done',
    failed: 'Failed',
    cancelled: 'Cancelled',
  }
  return labels[job.value?.stage] || (job.value ? 'Working...' : '')
})

const stagePercent = computed(() => job.value?.progress ?? 0)

watch(
  () => props.show,
  (visible) => {
    if (visible) summaryStore.loadHistory(20)
  },
  { immediate: true }
)

const openCitation = (page) => {
  const docId = job.value?.document_id
  if (!docId || !page) return
  pdfState.value = {
    url: '/media/data_source/' + encodeURIComponent(docId),
    page,
    highlight: '',
  }
  showPdf.value = true
}

const copyMarkdown = async () => {
  const markdown = job.value?.result_markdown || ''
  if (!markdown) return
  try {
    await navigator.clipboard.writeText(markdown)
  } catch (err) {
    console.error('Failed to copy markdown:', err)
  }
}

const handleClose = () => {
  emit('close')
}

const selectHistory = async (item) => {
  activeTab.value = 'result'
  await summaryStore.loadJob(item.id)
}

const handleRetry = async (item) => {
  await summaryStore.loadJob(item.id)
  await summaryStore.retryActive()
}

const handleRemove = async (item) => {
  await summaryStore.remove(item.id)
}
</script>

<template>
  <div class="summary-viewer">
    <div class="viewer-tabs">
      <button
        class="viewer-tab"
        :class="{ active: activeTab === 'result' }"
        @click="activeTab = 'result'"
      >
        Result
      </button>
      <button
        class="viewer-tab"
        :class="{ active: activeTab === 'history' }"
        @click="activeTab = 'history'"
      >
        History ({{ history.length }})
      </button>
    </div>

    <div v-if="activeTab === 'result'" class="viewer-result">
      <div v-if="!job" class="viewer-empty">
        No summary yet. Generate one from the Summarize PDF tool.
      </div>

      <template v-else>
        <div v-if="isActive" class="viewer-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: stagePercent + '%' }"></div>
          </div>
          <p class="progress-label">
            {{ stageLabel }} — {{ stagePercent }}%
          </p>
          <button class="viewer-btn danger" @click="summaryStore.cancelActive">
            Cancel
          </button>
        </div>

        <div v-if="job.status === 'failed'" class="viewer-error">
          <p><strong>Summary failed</strong> ({{ job.error_code }})</p>
          <p>{{ job.error_message }}</p>
          <button class="viewer-btn" @click="summaryStore.retryActive">Retry</button>
        </div>

        <div v-if="job.status === 'interrupted'" class="viewer-error">
          <p><strong>Summary interrupted</strong> — the server restarted mid-run.</p>
          <button class="viewer-btn" @click="summaryStore.retryActive">Retry</button>
        </div>

        <div v-if="job.status === 'completed' && job.result_json" class="viewer-result-body">
          <p class="overview">{{ job.result_json.overview }}</p>
          <section v-for="section in resultSections" :key="section.title" class="topic-section">
            <h3>{{ section.title }}</h3>
            <ul class="topic-points">
              <li v-for="point in section.points" :key="point.text">
                <span>{{ point.text }}</span>
                <button
                  v-for="page in point.pages"
                  :key="page"
                  class="page-badge"
                  @click="openCitation(page)"
                >
                  p.{{ page }}
                </button>
              </li>
            </ul>
          </section>
          <p v-if="job.result_json.skipped_topics?.length" class="skipped-note">
            Topics with no matching content: {{ job.result_json.skipped_topics.join(', ') }}
          </p>
          <div class="viewer-actions">
            <button class="viewer-btn" @click="copyMarkdown">Copy Markdown</button>
          </div>
        </div>

        <div v-else-if="partialSections.length" class="viewer-result-body">
          <p class="partial-note">Partial output — still generating...</p>
          <section v-for="section in partialSections" :key="section.title" class="topic-section">
            <h3>{{ section.title }}</h3>
            <ul class="topic-points">
              <li v-for="point in section.points" :key="point.text">{{ point.text }}</li>
            </ul>
          </section>
        </div>
      </template>
    </div>

    <div v-else class="viewer-history">
      <div v-if="!history.length" class="viewer-empty">No summary history.</div>
      <div v-for="item in history" :key="item.id" class="history-item">
        <div class="history-info">
          <span class="history-doc" :title="item.document_id">{{ item.document_id }}</span>
          <span class="history-status" :class="'status-' + item.status">{{ item.status }}</span>
          <span class="history-date">{{ new Date(item.created_at).toLocaleString() }}</span>
        </div>
        <div class="history-actions">
          <button class="viewer-btn" @click="selectHistory(item)">Open</button>
          <button
            v-if="['failed', 'interrupted', 'cancelled'].includes(item.status)"
            class="viewer-btn"
            @click="handleRetry(item)"
          >
            Retry
          </button>
          <button class="viewer-btn danger" @click="handleRemove(item)">Delete</button>
        </div>
      </div>
    </div>

    <PdfViewer
      :show="showPdf"
      :pdf-url="pdfState.url"
      :target-page="pdfState.page"
      @close="showPdf = false"
    />
  </div>
</template>

<style scoped>
.summary-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 320px;
}

.viewer-tabs {
  display: flex;
  gap: 8px;
}

.viewer-tab {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-size: 12px;
  cursor: pointer;
}

.viewer-tab.active {
  background: var(--primary-container);
  color: var(--on-primary);
}

.viewer-empty {
  padding: 24px;
  text-align: center;
  color: var(--on-surface-variant);
  font-size: 13px;
}

.viewer-progress {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-bar {
  height: 8px;
  border-radius: 4px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s ease;
}

.progress-label {
  margin: 0;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.viewer-error {
  padding: 14px;
  border-radius: 10px;
  background: var(--tertiary-container);
  border: 1px solid var(--tertiary);
  color: var(--on-tertiary);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.viewer-error p {
  margin: 0;
}

.viewer-result-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overview {
  font-size: 13px;
  color: var(--on-surface);
  margin: 0;
}

.topic-section h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--on-surface);
}

.topic-points {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.topic-points li {
  font-size: 12px;
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.page-badge {
  border: 1px solid var(--primary);
  background: var(--primary-container);
  color: var(--on-primary);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 10px;
  cursor: pointer;
}

.page-badge:hover {
  background: var(--primary);
}

.skipped-note,
.partial-note {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.viewer-actions {
  display: flex;
  gap: 8px;
}

.viewer-btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 12px;
  cursor: pointer;
}

.viewer-btn.danger {
  border-color: var(--tertiary);
  color: var(--on-tertiary);
}

.viewer-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
}

.history-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.history-doc {
  font-size: 12px;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.history-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--surface-container);
  color: var(--on-surface-variant);
}

.history-status.status-failed {
  background: var(--tertiary-container);
  color: var(--on-tertiary);
}

.history-date {
  font-size: 10px;
  color: var(--on-surface-variant);
}

.history-actions {
  display: flex;
  gap: 6px;
}
</style>
