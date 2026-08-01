<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getFiles, getRagDemoTrace } from '../../services/api'
import RagFlowStage from './RagFlowStage.vue'

defineEmits(['close'])

const STORAGE_KEY = 'rag-demo-trace'
const query = ref('What is retrieval augmented generation?')
const trace = ref(null)
const activeIndex = ref(0)
const isLoading = ref(false)
const isPlaying = ref(false)
const playSpeed = ref(1)
const technicalView = ref(false)
const drawerCollapsed = ref(false)
const error = ref('')
const timers = []
const availableDocs = ref([])
const selectedSources = ref([])
const topK = ref(5)
const stageEls = ref({})
const flowMain = ref(null)

const stages = computed(() => trace.value?.stages || [])
const activeStage = computed(() => stages.value[activeIndex.value] || null)
const maxDuration = computed(() =>
  Math.max(...stages.value.map(s => Number(s.duration_ms || 0)), 1)
)
const progress = computed(() =>
  stages.value.length ? Math.round(((activeIndex.value + 1) / stages.value.length) * 100) : 0
)

const clearTimers = () => {
  while (timers.length) {
    clearTimeout(timers.pop())
  }
}

const loadDocuments = async () => {
  try {
    const data = await getFiles()
    availableDocs.value = (data.files || data || []).map((f) =>
      typeof f === 'string' ? { name: f, filename: f } : f
    )
  } catch {
    availableDocs.value = []
  }
}

const loadSavedTrace = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      trace.value = saved.trace
      query.value = saved.query || query.value
      selectedSources.value = saved.sources || []
      topK.value = saved.topK || 5
    }
  } catch {
    // ignore
  }
}

const saveTrace = () => {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        trace: trace.value,
        query: query.value,
        sources: selectedSources.value,
        topK: topK.value,
      })
    )
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadDocuments()
  loadSavedTrace()
})

const stageDelay = (stage) => {
  const realDuration = Number(stage?.duration_ms || 0)
  return Math.min(Math.max(realDuration, 900), 1800)
}

const scrollToActive = () => {
  const el = stageEls.value[activeIndex.value]
  if (el?.scrollIntoView) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const scheduleNext = (index) => {
  if (index >= stages.value.length - 1) {
    isPlaying.value = false
    return
  }
  const timer = setTimeout(() => {
    activeIndex.value = index + 1
    scheduleNext(activeIndex.value)
  }, stageDelay(stages.value[index]) / playSpeed.value)
  timers.push(timer)
}

const playTrace = () => {
  clearTimers()
  if (!stages.value.length) return
  activeIndex.value = 0
  isPlaying.value = true
  scheduleNext(0)
}

const togglePlay = () => {
  if (!stages.value.length) return
  if (isPlaying.value) {
    clearTimers()
    isPlaying.value = false
  } else {
    if (activeIndex.value >= stages.value.length - 1) {
      activeIndex.value = 0
    }
    isPlaying.value = true
    scheduleNext(activeIndex.value)
  }
}

const stepBackward = () => {
  clearTimers()
  isPlaying.value = false
  activeIndex.value = Math.max(activeIndex.value - 1, 0)
}

const stepForward = () => {
  clearTimers()
  isPlaying.value = false
  activeIndex.value = Math.min(activeIndex.value + 1, stages.value.length - 1)
}

const replay = () => {
  if (trace.value) {
    playTrace()
  }
}

const runDemo = async () => {
  const trimmedQuery = query.value.trim()
  if (!trimmedQuery) {
    error.value = 'Enter a question to run the demo.'
    return
  }

  clearTimers()
  isLoading.value = true
  isPlaying.value = false
  error.value = ''

  try {
    const payload = {
      query: trimmedQuery,
      top_k: topK.value,
      include_answer: true,
    }
    if (selectedSources.value.length > 0) {
      payload.sources = selectedSources.value
    }
    trace.value = await getRagDemoTrace(payload)
    activeIndex.value = 0
    saveTrace()
    playTrace()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to run RAG demo.'
  } finally {
    isLoading.value = false
  }
}

const selectStage = (index) => {
  clearTimers()
  isPlaying.value = false
  activeIndex.value = index
}

const exportTrace = () => {
  if (!trace.value) return
  const blob = new Blob([JSON.stringify(trace.value, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rag-trace-${trace.value.trace_id || Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const onStageEl = (el, index) => {
  stageEls.value[index] = el
}

watch(activeIndex, () => {
  nextTick(scrollToActive)
})

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <section class="rag-demo-view">
    <header class="demo-header">
      <div class="header-text">
        <span class="eyebrow">Live Demo</span>
        <h1>RAG Trace Visualization</h1>
        <p>Watch a question move through retrieval, ranking, context building, and answer generation.</p>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="ghost-btn"
          :disabled="!trace"
          @click="exportTrace"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
          </svg>
          Export JSON
        </button>
        <button type="button" class="ghost-btn" @click="$emit('close')">
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
          </svg>
          Back to Workspace
        </button>
      </div>
    </header>

    <div class="demo-body">
      <!-- Control drawer -->
      <aside class="control-drawer" :class="{ collapsed: drawerCollapsed }">
        <button
          type="button"
          class="drawer-toggle"
          :aria-label="drawerCollapsed ? 'Expand controls' : 'Collapse controls'"
          @click="drawerCollapsed = !drawerCollapsed"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path :d="drawerCollapsed ? 'M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z' : 'M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z'" />
          </svg>
        </button>

        <div v-show="!drawerCollapsed" class="drawer-content">
          <div class="drawer-section">
            <span class="drawer-label">Question</span>
            <input
              v-model="query"
              type="text"
              class="drawer-input"
              placeholder="Ask anything about the lectures..."
              :disabled="isLoading"
              @keyup.enter="runDemo"
            >
          </div>

          <div class="drawer-section">
            <span class="drawer-label">Sources</span>
            <div class="source-list">
              <label v-for="doc in availableDocs" :key="doc.filename || doc.name" class="source-item">
                <input
                  v-model="selectedSources"
                  type="checkbox"
                  :value="doc.filename || doc.name"
                  :disabled="isLoading"
                >
                <span class="source-name">{{ doc.name || doc.filename }}</span>
              </label>
              <p v-if="availableDocs.length === 0" class="drawer-muted">No documents indexed yet.</p>
            </div>
          </div>

          <div class="drawer-section">
            <div class="drawer-label-row">
              <span class="drawer-label">Top K</span>
              <span class="drawer-value">{{ topK }}</span>
            </div>
            <input
              v-model.number="topK"
              type="range"
              min="1"
              max="10"
              step="1"
              class="drawer-range"
              :disabled="isLoading"
            >
          </div>

          <div class="drawer-section">
            <span class="drawer-label">Playback</span>
            <div class="play-controls">
              <button
                type="button"
                class="icon-btn"
                aria-label="Step backward"
                :disabled="!trace || activeIndex === 0"
                @click="stepBackward"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" /></svg>
              </button>
              <button
                type="button"
                class="play-btn"
                :disabled="!trace || isLoading"
                @click="togglePlay"
              >
                <svg v-if="isPlaying" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>
                <svg v-else viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
              </button>
              <button
                type="button"
                class="icon-btn"
                aria-label="Step forward"
                :disabled="!trace || activeIndex >= stages.length - 1"
                @click="stepForward"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" /></svg>
              </button>
            </div>
            <div class="speed-row">
              <button
                v-for="speed in [0.5, 1, 2]"
                :key="speed"
                type="button"
                class="speed-btn"
                :class="{ active: playSpeed === speed }"
                @click="playSpeed = speed"
              >
                {{ speed }}x
              </button>
            </div>
          </div>

          <div class="drawer-section">
            <label class="toggle-row">
              <input v-model="technicalView" type="checkbox">
              <span class="toggle-track" aria-hidden="true" />
              <span class="toggle-text">Technical view</span>
            </label>
          </div>

          <div class="drawer-actions">
            <button type="button" class="primary-btn" :disabled="isLoading" @click="runDemo">
              {{ isLoading ? 'Running...' : 'Run Demo' }}
            </button>
            <button type="button" class="secondary-btn" :disabled="!trace || isLoading" @click="replay">
              Replay
            </button>
          </div>
        </div>
      </aside>

      <!-- Vertical flow main area -->
      <main ref="flowMain" class="flow-main">
        <div v-if="!trace" class="empty-state">
          <span class="eyebrow">Ready</span>
          <h2>Run a demo trace</h2>
          <p>Enter a question on the left, then watch each RAG stage light up as the pipeline runs.</p>
        </div>

        <div v-else class="flow-progress" aria-hidden="true">
          <span class="flow-progress-label">
            Stage {{ activeIndex + 1 }} / {{ stages.length }}
            <template v-if="activeStage"> · {{ activeStage.title }}</template>
          </span>
          <div class="flow-progress-track">
            <span class="flow-progress-fill" :style="{ width: `${progress}%` }" />
          </div>
        </div>

        <div v-if="error" class="demo-error" role="alert">{{ error }}</div>

        <div v-if="stages.length" class="flow-list">
          <RagFlowStage
            v-for="(stage, index) in stages"
            :key="stage.id"
            :stage="stage"
            :index="index"
            :active="index === activeIndex"
            :played="index < activeIndex"
            :technical-view="technicalView"
            :max-duration="maxDuration"
            @stage-el="onStageEl"
            @click="selectStage(index)"
          />
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.rag-demo-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--surface);
}

/* Header */
.demo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 22px;
  border-bottom: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  flex-wrap: wrap;
}

.header-text h1,
.header-text p {
  margin: 0;
}

.header-text h1 {
  margin-bottom: 4px;
  font-size: 22px;
  color: var(--text-main);
}

.header-text p {
  color: var(--text-muted);
  font-size: 13px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--text-main);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.ghost-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.ghost-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ghost-btn svg {
  width: 15px;
  height: 15px;
}

/* Body layout */
.demo-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
}

/* Control drawer */
.control-drawer {
  display: flex;
  flex-direction: column;
  background: var(--surface-container-low);
  border-right: 1px solid var(--outline-variant);
  overflow-y: auto;
  transition: all 0.2s ease;
}

.control-drawer.collapsed {
  width: 48px;
  overflow: hidden;
}

.drawer-toggle {
  align-self: flex-end;
  width: 32px;
  height: 32px;
  margin: 10px;
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  background: var(--surface-container);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.drawer-toggle:hover {
  color: var(--text-main);
  border-color: var(--accent);
}

.drawer-toggle svg {
  width: 16px;
  height: 16px;
}

.drawer-content {
  padding: 4px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 232px;
}

.drawer-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.drawer-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.drawer-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.drawer-value {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
}

.drawer-input {
  width: 100%;
  height: 38px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--text-main);
  padding: 0 12px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.drawer-input:focus {
  border-color: var(--accent);
}

.source-list {
  max-height: 150px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  background: var(--surface-container);
  padding: 6px;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  transition: background-color 0.12s;
}

.source-item:hover {
  background: rgba(129, 140, 248, 0.1);
}

.source-item input {
  accent-color: var(--accent);
  flex-shrink: 0;
}

.source-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-muted {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  padding: 4px 8px;
}

.drawer-range {
  width: 100%;
  height: 5px;
  border-radius: 3px;
  background: var(--surface-container-high);
  -webkit-appearance: none;
  appearance: none;
  outline: none;
}

.drawer-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--surface-container-low);
  cursor: pointer;
}

/* Playback */
.play-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.icon-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-btn svg {
  width: 16px;
  height: 16px;
}

.play-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s, filter 0.15s;
}

.play-btn:hover:not(:disabled) {
  transform: scale(1.06);
  filter: brightness(1.1);
}

.play-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.play-btn svg {
  width: 18px;
  height: 18px;
}

.speed-row {
  display: flex;
  gap: 6px;
}

.speed-btn {
  flex: 1;
  padding: 5px 0;
  border-radius: 7px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--text-muted);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.speed-btn.active {
  background: rgba(99, 102, 241, 0.15);
  border-color: var(--accent);
  color: var(--accent);
}

/* Toggle */
.toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.toggle-row input {
  display: none;
}

.toggle-track {
  width: 36px;
  height: 20px;
  border-radius: 999px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  position: relative;
  transition: all 0.2s;
}

.toggle-track::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: all 0.2s;
}

.toggle-row input:checked + .toggle-track {
  background: rgba(99, 102, 241, 0.3);
  border-color: var(--accent);
}

.toggle-row input:checked + .toggle-track::after {
  left: 18px;
  background: var(--accent);
}

.toggle-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

/* Drawer actions */
.drawer-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.primary-btn,
.secondary-btn {
  height: 38px;
  border-radius: 8px;
  border: 1px solid transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.primary-btn {
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
}

.primary-btn:hover:not(:disabled) {
  filter: brightness(1.08);
}

.secondary-btn {
  background: var(--surface-container);
  color: var(--text-main);
  border-color: var(--outline-variant);
}

.secondary-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Flow main area */
.flow-main {
  min-width: 0;
  overflow-y: auto;
  padding: 20px 28px 40px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  margin: auto;
  text-align: center;
  max-width: 420px;
}

.empty-state h2 {
  margin: 0 0 8px;
  font-size: 26px;
  color: var(--text-main);
}

.empty-state p {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.6;
}

.flow-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--surface);
  padding: 8px 0;
}

.flow-progress-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.flow-progress-track {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.flow-progress-fill {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  transition: width 0.35s ease;
}

.demo-error {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.28);
  font-size: 13px;
}

.flow-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 900px) {
  .demo-body {
    grid-template-columns: 1fr;
  }

  .control-drawer {
    border-right: none;
    border-bottom: 1px solid var(--outline-variant);
    max-height: 320px;
  }

  .control-drawer.collapsed {
    width: auto;
    max-height: 52px;
  }

  .drawer-content {
    min-width: 0;
  }
}
</style>
