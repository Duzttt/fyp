<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getAdminDocumentChunks, getAdminDocuments } from '../../services/api'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])

const documents = ref([])
const selectedDoc = ref(null)
const chunks = ref([])
const isLoading = ref(false)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20

// Document-level totals (server computes across the whole document)
const totalChunks = ref(0)
const totalChars = ref(0)

// Search + interaction state
const searchQuery = ref('')
const expandedChunks = ref(new Set())
const copiedIndex = ref(null)
const jumpToPage = ref('')
let searchTimer = null

// Stats (document level, not just the current page)
const stats = computed(() => {
  if (!selectedDoc.value || totalChunks.value === 0) return null
  const start = (currentPage.value - 1) * pageSize + 1
  const end = Math.min(start + chunks.value.length - 1, totalChunks.value)
  return {
    total: totalChunks.value,
    totalChars: totalChars.value,
    start,
    end,
    shown: chunks.value.length,
    avgSize: totalChars.value ? Math.round(totalChars.value / totalChunks.value) : 0,
  }
})

// Size distribution histogram (current page)
const sizeBuckets = computed(() => {
  const buckets = [
    { label: '<200', min: 0, max: 199, count: 0 },
    { label: '200-300', min: 200, max: 299, count: 0 },
    { label: '300-400', min: 300, max: 399, count: 0 },
    { label: '400-500', min: 400, max: 499, count: 0 },
    { label: '500+', min: 500, max: Infinity, count: 0 },
  ]
  for (const chunk of chunks.value) {
    const len = chunk.text?.length || 0
    const bucket = buckets.find(b => len >= b.min && len <= b.max)
    if (bucket) bucket.count++
  }
  const max = Math.max(...buckets.map(b => b.count), 1)
  return buckets.map(b => ({ ...b, pct: Math.round((b.count / max) * 100) }))
})

const fetchDocuments = async () => {
  try {
    const response = await getAdminDocuments()
    documents.value = response.documents || []
  } catch (err) {
    console.error('Failed to fetch documents:', err)
    error.value = 'Failed to load documents'
  }
}

const fetchChunks = async () => {
  if (!selectedDoc.value) return

  isLoading.value = true
  error.value = ''

  try {
    const docId = selectedDoc.value.name || selectedDoc.value.filename
    const response = await getAdminDocumentChunks(
      docId,
      currentPage.value,
      pageSize,
      searchQuery.value.trim()
    )
    chunks.value = response.chunks || []
    totalChunks.value = response.total || 0
    totalChars.value = response.total_chars || 0
    totalPages.value = response.total_pages || 1
    if (currentPage.value > totalPages.value) {
      currentPage.value = Math.max(totalPages.value, 1)
    }
  } catch (err) {
    console.error('Failed to fetch chunks:', err)
    error.value = 'Failed to load chunks'
    chunks.value = []
    totalChunks.value = 0
    totalChars.value = 0
  } finally {
    isLoading.value = false
  }
}

watch(selectedDoc, () => {
  currentPage.value = 1
  expandedChunks.value = new Set()
  fetchChunks()
})

watch(currentPage, () => {
  fetchChunks()
})

watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    expandedChunks.value = new Set()
    fetchChunks()
  }, 300)
})

watch(() => props.show, (newVal) => {
  if (newVal && documents.value.length === 0) {
    fetchDocuments()
  }
})

onMounted(() => {
  if (props.show) {
    fetchDocuments()
  }
})

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
})

const getChunkColor = (index) => {
  const colors = [
    'rgba(99, 102, 241, 0.15)',
    'rgba(236, 72, 153, 0.15)',
    'rgba(34, 197, 94, 0.15)',
    'rgba(234, 179, 8, 0.15)',
    'rgba(168, 85, 247, 0.15)',
    'rgba(14, 165, 233, 0.15)',
    'rgba(249, 115, 22, 0.15)',
    'rgba(239, 68, 68, 0.15)',
  ]
  return colors[index % colors.length]
}

const getChunkBorderColor = (index) => {
  const colors = [
    'rgba(99, 102, 241, 0.4)',
    'rgba(236, 72, 153, 0.4)',
    'rgba(34, 197, 94, 0.4)',
    'rgba(234, 179, 8, 0.4)',
    'rgba(168, 85, 247, 0.4)',
    'rgba(14, 165, 233, 0.4)',
    'rgba(249, 115, 22, 0.4)',
    'rgba(239, 68, 68, 0.4)',
  ]
  return colors[index % colors.length]
}

const formatSize = (chars) => {
  if (chars < 1024) return `${chars} chars`
  return `${(chars / 1024).toFixed(1)}K chars`
}

const isExpanded = (key) => expandedChunks.value.has(key)

const clippedText = (text) => {
  const value = text || '(empty)'
  return value.length > 260 ? `${value.slice(0, 260)}…` : value
}

const toggleExpand = (index) => {
  const next = new Set(expandedChunks.value)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  expandedChunks.value = next
}

const copyChunk = async (index) => {
  const text = chunks.value[index]?.text || ''
  try {
    await navigator.clipboard.writeText(text)
    copiedIndex.value = index
    setTimeout(() => {
      if (copiedIndex.value === index) copiedIndex.value = null
    }, 1500)
  } catch {
    // clipboard unavailable
  }
}

const jumpPage = () => {
  const target = parseInt(jumpToPage.value, 10)
  if (!Number.isFinite(target)) return
  currentPage.value = Math.min(Math.max(target, 1), totalPages.value)
  jumpToPage.value = ''
}

const resultStartIndex = computed(() => (currentPage.value - 1) * pageSize + 1)
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="chunkviz-overlay" @click.self="emit('close')">
        <div class="chunkviz-modal">
          <!-- Header -->
          <div class="modal-header">
            <div class="header-title">
              <svg class="header-icon" viewBox="0 0 24 24" fill="none">
                <path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5zm10 0a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1V5zM4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-4zm10 0a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4z" stroke="currentColor" stroke-width="1.5"/>
              </svg>
              <div>
                <h2>Chunk Visualizer</h2>
                <span class="header-sub">Inspect how your documents are split for retrieval</span>
              </div>
            </div>
            <button class="close-btn" @click="emit('close')" title="Close" aria-label="Close visualization">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="modal-content">
            <!-- Document Selector -->
            <div class="section doc-selector">
              <label class="section-label">Select Document</label>
              <select v-model="selectedDoc" class="doc-select">
                <option :value="null" disabled>Choose a document...</option>
                <option
                  v-for="doc in documents"
                  :key="doc.name || doc.filename"
                  :value="doc"
                >
                  {{ doc.name || doc.filename }} ({{ doc.chunk_count || '?' }} chunks)
                </option>
              </select>
            </div>

            <!-- Document-level stats -->
            <div v-if="stats" class="section stats-panel">
              <div class="section-header">
                <label class="section-label">Overview</label>
                <span v-if="searchQuery" class="filter-badge">
                  Filtered by "{{ searchQuery }}"
                </span>
              </div>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-value">{{ stats.total }}</span>
                  <span class="stat-label">Chunks</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ formatSize(stats.totalChars) }}</span>
                  <span class="stat-label">Total Size</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ formatSize(stats.avgSize) }}</span>
                  <span class="stat-label">Avg Size</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ stats.start }}-{{ stats.end }}</span>
                  <span class="stat-label">Showing</span>
                </div>
              </div>
            </div>

            <!-- Size distribution -->
            <div v-if="sizeBuckets.some(b => b.count > 0)" class="section dist-section">
              <label class="section-label">Size Distribution (this page)</label>
              <div class="dist-bars">
                <div v-for="bucket in sizeBuckets" :key="bucket.label" class="dist-col">
                  <span class="dist-count">{{ bucket.count }}</span>
                  <div class="dist-track">
                    <span class="dist-fill" :style="{ height: `${bucket.pct}%` }" />
                  </div>
                  <span class="dist-label">{{ bucket.label }}</span>
                </div>
              </div>
            </div>

            <!-- Toolbar: search + pagination -->
            <div class="section chunks-section">
              <div class="section-header">
                <label class="section-label">Chunks</label>
                <div class="toolbar">
                  <div class="search-wrap">
                    <svg class="search-icon" viewBox="0 0 24 24" fill="none">
                      <path d="M21 21l-4.35-4.35M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    <input
                      v-model="searchQuery"
                      type="text"
                      class="search-input"
                      placeholder="Filter chunks..."
                      aria-label="Filter chunks by text"
                    >
                  </div>
                  <div v-if="totalPages > 1" class="pagination">
                    <button
                      class="page-btn"
                      :disabled="currentPage === 1"
                      aria-label="Previous page"
                      @click="currentPage--"
                    >
                      ←
                    </button>
                    <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
                    <button
                      class="page-btn"
                      :disabled="currentPage === totalPages"
                      aria-label="Next page"
                      @click="currentPage++"
                    >
                      →
                    </button>
                    <div class="jump-wrap">
                      <input
                        v-model="jumpToPage"
                        type="number"
                        min="1"
                        :max="totalPages"
                        class="jump-input"
                        placeholder="Go"
                        aria-label="Jump to page"
                        @keyup.enter="jumpPage"
                      >
                    </div>
                  </div>
                </div>
              </div>

              <!-- Loading -->
              <div v-if="isLoading" class="loading-state">
                <div class="spinner"></div>
                <span>Loading chunks...</span>
              </div>

              <!-- Error -->
              <div v-else-if="error" class="error-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M12 9v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>{{ error }}</span>
              </div>

              <!-- No selection -->
              <div v-else-if="!selectedDoc" class="empty-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M9 12h6m-3-3v6m-7 4h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>Select a document to visualize chunks</span>
              </div>

              <!-- No results -->
              <div v-else-if="chunks.length === 0" class="empty-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M9 12h6m-3-3v6m-7 4h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span v-if="searchQuery">No chunks match "{{ searchQuery }}"</span>
                <span v-else>No chunks found for this document</span>
              </div>

              <!-- Chunks list -->
              <div v-else class="chunks-list">
                <div
                  v-for="(chunk, index) in chunks"
                  :key="chunk.index ?? index"
                  class="chunk-item"
                  :class="{ expanded: isExpanded(chunk.index ?? index) }"
                  :style="{
                    backgroundColor: getChunkColor(index),
                    borderColor: getChunkBorderColor(index)
                  }"
                >
                  <div class="chunk-header">
                    <div class="chunk-title-group">
                      <span class="chunk-index">#{{ resultStartIndex + index }}</span>
                      <span class="chunk-meta">
                        <span v-if="chunk.page !== undefined" class="chunk-page">Page {{ chunk.page }}</span>
                        <span class="chunk-size">{{ chunk.text?.length || 0 }} chars</span>
                        <span v-if="chunk.index !== undefined" class="chunk-pos">idx {{ chunk.index }}</span>
                      </span>
                    </div>
                    <div class="chunk-actions">
                      <button
                        type="button"
                        class="icon-action"
                        aria-label="Copy chunk text"
                        title="Copy text"
                        @click.stop="copyChunk(index)"
                      >
                        <svg v-if="copiedIndex === index" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                        </svg>
                        <svg v-else viewBox="0 0 24 24" fill="currentColor">
                          <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div class="chunk-text">
                    {{ isExpanded(chunk.index ?? index) ? (chunk.text || '(empty)') : clippedText(chunk.text) }}
                  </div>
                  <button
                    v-if="(chunk.text?.length || 0) > 260"
                    type="button"
                    class="expand-btn"
                    @click.stop="toggleExpand(chunk.index ?? index)"
                  >
                    {{ isExpanded(chunk.index ?? index) ? 'Show less' : 'Show more' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.chunkviz-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.chunkviz-modal {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 16px;
  width: 100%;
  max-width: 960px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
}

/* Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--outline-variant);
  background: var(--surface-container);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 24px;
  height: 24px;
  color: var(--accent);
}

.modal-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
}

.header-sub {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--outline-variant);
  background: rgba(128, 128, 128, 0.1);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(128, 128, 128, 0.2);
  color: var(--text-main);
}

.close-btn svg {
  width: 18px;
  height: 18px;
}

/* Content */
.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-badge {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}

/* Document Selector */
.doc-select {
  width: 100%;
  padding: 10px 14px;
  background: var(--surface-container-lowest);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
  color: var(--text-main);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.doc-select:hover {
  border-color: var(--accent);
}

.doc-select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.doc-select option {
  background: var(--surface-container);
  color: var(--text-main);
}

/* Stats Panel */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  background: var(--surface-container-low);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 19px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Size distribution */
.dist-bars {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px;
  background: var(--surface-container-low);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  min-height: 110px;
}

.dist-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.dist-track {
  width: 100%;
  max-width: 44px;
  height: 60px;
  display: flex;
  align-items: flex-end;
  border-radius: 6px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.dist-fill {
  display: block;
  width: 100%;
  border-radius: 6px;
  background: linear-gradient(180deg, var(--accent), #a855f7);
  transition: height 0.3s ease;
}

.dist-count {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-main);
}

.dist-label {
  font-size: 10px;
  color: var(--text-muted);
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 220px;
  height: 32px;
  padding: 0 12px 0 32px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}

.search-input:focus {
  border-color: var(--accent);
}

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  border-radius: 7px;
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  transition: all 0.15s;
}

.page-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 56px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.jump-wrap {
  display: flex;
  align-items: center;
}

.jump-input {
  width: 52px;
  height: 28px;
  padding: 0 8px;
  border-radius: 7px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}

.jump-input:focus {
  border-color: var(--accent);
}

/* States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-muted);
  text-align: center;
}

.loading-state svg,
.error-state svg,
.empty-state svg {
  width: 40px;
  height: 40px;
  opacity: 0.5;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  color: #fca5a5;
}

.error-state svg {
  color: #fca5a5;
  opacity: 1;
}

/* Chunks List */
.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 8px;
}

.chunks-list::-webkit-scrollbar {
  width: 6px;
}

.chunks-list::-webkit-scrollbar-track {
  background: var(--surface-container-low);
  border-radius: 3px;
}

.chunks-list::-webkit-scrollbar-thumb {
  background: var(--outline-variant);
  border-radius: 3px;
}

.chunk-item {
  border: 1px solid;
  border-radius: 12px;
  padding: 12px 14px;
  transition: transform 0.15s, border-color 0.15s;
}

.chunk-item:hover {
  transform: translateX(4px);
}

.chunk-item.expanded {
  border-color: var(--accent);
}

.chunk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.chunk-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.chunk-index {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
}

.chunk-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
  min-width: 0;
}

.chunk-page,
.chunk-pos {
  background: var(--surface-container-high);
  padding: 2px 8px;
  border-radius: 999px;
}

.chunk-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.icon-action {
  width: 26px;
  height: 26px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.icon-action:hover {
  background: var(--surface-container-high);
  color: var(--text-main);
  border-color: var(--outline-variant);
}

.icon-action svg {
  width: 14px;
  height: 14px;
}

.chunk-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.expand-btn {
  margin-top: 8px;
  padding: 3px 10px;
  border: 1px solid var(--outline-variant);
  border-radius: 999px;
  background: var(--surface-container-high);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.expand-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

/* Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .chunkviz-modal,
.modal-leave-to .chunkviz-modal {
  transform: scale(0.95) translateY(20px);
}

/* Responsive */
@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .chunkviz-modal {
    max-height: 92vh;
  }

  .search-input {
    width: 100%;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
