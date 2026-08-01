<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  chunks: {
    type: Array,
    default: () => [],
  },
  query: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['chunk-click', 'chunk-rightclick'])

const isOpen = ref(false)
const expandedChunks = ref(new Set())
const showAllChunks = ref(false)
const hoveredChunk = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })

const SIMILARITY_THRESHOLD = 0.6

const HIGHLIGHT_STOP_WORDS = new Set([
  'about', 'after', 'again', 'also', 'any', 'are', 'because', 'been', 'before',
  'being', 'between', 'both', 'can', 'could', 'did', 'does', 'doing', 'each',
  'explain', 'for', 'from', 'had', 'has', 'have', 'how', 'into', 'its', 'just',
  'key', 'main', 'more', 'most', 'much', 'not', 'only', 'other', 'our', 'out',
  'over', 'points', 'should', 'some', 'such', 'than', 'that', 'the', 'their',
  'them', 'then', 'there', 'these', 'they', 'this', 'those', 'through', 'under',
  'very', 'was', 'were', 'what', 'when', 'where', 'which', 'while', 'who',
  'why', 'will', 'with', 'would', 'you',
])

const highlightKeywords = computed(() => {
  const tokens = (props.query || '').toLowerCase().match(/[a-z0-9]{3,}/g) || []
  return Array.from(new Set(tokens.filter((t) => !HIGHLIGHT_STOP_WORDS.has(t)))).slice(0, 8)
})

const escapeHtml = (s) =>
  String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const escapeRegExp = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const highlight = (text) => {
  let result = escapeHtml(text)
  highlightKeywords.value.forEach((kw) => {
    const pattern = new RegExp(`(${escapeRegExp(escapeHtml(kw))})`, 'gi')
    result = result.replace(pattern, '<mark class="kw-hit">$1</mark>')
  })
  return result
}

const displayName = (source) => {
  if (!source) return 'Unknown'
  const base = String(source).split('/').pop()
  return base.replace(/\.pdf$/i, '')
}

const sourceCount = computed(() => {
  if (!props.chunks.length) return 0
  return new Set(props.chunks.map((c) => c.source)).size
})

const copiedChunk = ref(null)
const copyChunk = async (chunk, index) => {
  try {
    await navigator.clipboard.writeText(chunk.text || '')
    copiedChunk.value = index
    setTimeout(() => {
      if (copiedChunk.value === index) copiedChunk.value = null
    }, 1500)
  } catch (_) {
    // clipboard unavailable — ignore
  }
}

const filteredChunks = computed(() => {
  if (!props.chunks || props.chunks.length === 0) {
    return []
  }

  if (showAllChunks.value) {
    return props.chunks
  }

  const strongMatches = props.chunks.filter(
    (chunk) => (chunk.score ?? 0) >= SIMILARITY_THRESHOLD,
  )

  if (strongMatches.length === 0) {
    return props.chunks
  }

  return strongMatches
})

const getScoreColor = (score) => {
  if (score >= 0.8) return '#22c55e'
  if (score >= 0.5) return '#eab308'
  return '#6b7280'
}

const getScoreColorClass = (score) => {
  if (score >= 0.8) return 'score-high'
  if (score >= 0.5) return 'score-medium'
  return 'score-low'
}

const toggleExpand = (index) => {
  const newSet = new Set(expandedChunks.value)
  if (newSet.has(index)) {
    newSet.delete(index)
  } else {
    newSet.add(index)
  }
  expandedChunks.value = newSet
}

const isExpanded = (index) => {
  return expandedChunks.value.has(index)
}

const handleChunkHover = (chunk, event) => {
  hoveredChunk.value = chunk
  const rect = event.target.getBoundingClientRect()
  const tooltipW = 400
  const tooltipH = 200
  let x = rect.left
  let y = rect.bottom + 10
  if (x + tooltipW > window.innerWidth) x = window.innerWidth - tooltipW - 8
  if (y + tooltipH > window.innerHeight) y = rect.top - tooltipH - 8
  if (x < 0) x = 8
  if (y < 0) y = 8
  tooltipPosition.value = { x, y }
}

const handleChunkLeave = () => {
  hoveredChunk.value = null
}

const handleChunkClick = (chunk) => {
  emit('chunk-click', chunk)
}

const handleChunkRightClick = (event, chunk) => {
  emit('chunk-rightclick', event, chunk)
}

const getRankLabel = (index) => {
  const rank = index + 1
  if (rank === 1) return 'Top match'
  return `#${rank}`
}
</script>

<template>
  <div v-if="loading" class="retrieval-loading" aria-live="polite">
    <div class="loading-spinner" aria-hidden="true"></div>
    <span>Searching knowledge base…</span>
  </div>
  
  <div v-else-if="filteredChunks.length > 0" class="retrieval-chunks">
    <div class="retrieval-header">
      <div class="retrieval-meta">
        <span class="retrieval-title">
          <svg class="title-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3.5C6.8 2.5 5 2.3 2.5 2.5v10c2.5-.2 4.3 0 5.5 1 1.2-1 3-.2 5.5-1v-10C11 2.3 9.2 2.5 8 3.5z"/><path d="M8 3.5v10"/></svg>
          Retrieved Context
        </span>
        <span class="retrieval-count">{{ filteredChunks.length }} of {{ chunks.length }} chunks</span>
        <span v-if="sourceCount > 0" class="retrieval-count source-count">
          {{ sourceCount }} doc{{ sourceCount > 1 ? 's' : '' }}
        </span>
      </div>

      <div class="retrieval-actions">
        <button
          v-if="chunks.length > filteredChunks.length"
          type="button"
          class="show-all-btn"
          @click.stop="showAllChunks = !showAllChunks"
        >
          {{ showAllChunks ? 'Show Relevant Only' : `Show All (${chunks.length})` }}
        </button>
        <button
          type="button"
          class="collapse-btn"
          :aria-expanded="isOpen"
          aria-controls="retrieval-chunks-body"
          @click.stop="isOpen = !isOpen"
        >
          <span class="collapse-icon" :class="{ 'is-open': isOpen }" aria-hidden="true">
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4.5L6 7.5l3-3"/></svg>
          </span>
          <span class="collapse-label">{{ isOpen ? 'Hide' : 'Show' }} context</span>
        </button>
      </div>
    </div>
    
    <div v-if="isOpen" id="retrieval-chunks-body" class="chunks-scroll">
      <div class="chunks-grid">
        <div
          v-for="(chunk, index) in filteredChunks"
          :key="index"
          class="chunk-card"
          :class="getScoreColorClass(chunk.score)"
          @mouseenter="handleChunkHover(chunk, $event)"
          @mouseleave="handleChunkLeave"
          @click="handleChunkClick(chunk)"
          @contextmenu="handleChunkRightClick($event, chunk)"
        >
          <div class="chunk-header">
            <span class="rank-badge" :class="'rank-' + (index < 3 ? index + 1 : 'other')">{{ getRankLabel(index) }}</span>
            <div class="chunk-score">
              <div
                class="score-badge"
                :style="{ backgroundColor: getScoreColor(chunk.score) }"
                :title="Math.round(chunk.score * 100) + '% similarity'"
              >
                {{ Math.round(chunk.score * 100) }}%
              </div>
            </div>
            <div class="chunk-source">
              <span class="source-name" :title="chunk.source">{{ displayName(chunk.source) }}</span>
              <span v-if="chunk.page" class="source-page">Page {{ chunk.page }}</span>
            </div>
            <button
              type="button"
              class="copy-chunk-btn"
              :aria-label="copiedChunk === index ? 'Copied to clipboard' : 'Copy chunk text'"
              :title="copiedChunk === index ? 'Copied!' : 'Copy chunk'"
              @click.stop="copyChunk(chunk, index)"
            >
              <svg v-if="copiedChunk === index" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button
              type="button"
              class="expand-btn"
              :aria-expanded="isExpanded(index)"
              :aria-label="isExpanded(index) ? 'Collapse chunk' : 'Expand chunk'"
              @click.stop="toggleExpand(index)"
            >
              <span class="expand-chevron" :class="{ 'is-open': isExpanded(index) }" aria-hidden="true">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4.5L6 7.5l3-3"/></svg>
              </span>
            </button>
          </div>

          <div class="chunk-progress">
            <div
              class="progress-bar"
              :style="{
                width: chunk.score * 100 + '%',
                background: `linear-gradient(90deg, ${getScoreColor(chunk.score)} 0%, ${getScoreColor(chunk.score)}80 100%)`,
              }"
            ></div>
          </div>

          <div class="chunk-content">
            <p class="chunk-preview" v-html="highlight(isExpanded(index) ? chunk.text : chunk.preview)"></p>
          </div>

          <div v-if="chunk.text.length > 100" class="chunk-footer">
            <span class="view-hint">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 12l4-4-4-4M14 8H6"/></svg>
              Click to view source PDF
            </span>
            <span class="char-count">
              {{ isExpanded(index) ? chunk.text.length : 100 }} / {{ chunk.text.length }} chars
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Chunk Preview Tooltip -->
    <Teleport to="body">
      <div
        v-if="hoveredChunk"
        class="chunk-tooltip"
        :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
      >
      <div class="chunk-tooltip-header">
        <span class="tooltip-source">
          <svg class="tooltip-file-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h5l3 3V14a.5.5 0 0 1-.5.5h-7.5A.5.5 0 0 1 3.5 14V2a.5.5 0 0 1 .5-.5z"/><path d="M9 1.5V5h3.5"/></svg>
          {{ displayName(hoveredChunk.source) }}
        </span>
        <span v-if="hoveredChunk.page" class="tooltip-page">· Page {{ hoveredChunk.page }}</span>
        <span class="tooltip-score" :style="{ color: getScoreColor(hoveredChunk.score) }">
          {{ Math.round(hoveredChunk.score * 100) }}% match
        </span>
      </div>
      <div class="chunk-tooltip-body">
        {{ hoveredChunk.text }}
      </div>
    </div>
    </Teleport>
  </div>
</template>

<style scoped>
.retrieval-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.retrieval-chunks {
  margin-top: 16px;
  padding: 16px;
  background: var(--card-bg);
  border-radius: 12px;
  border: 1px solid var(--card-border);
}

.retrieval-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.retrieval-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.retrieval-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.retrieval-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.title-icon {
  width: 14px;
  height: 14px;
  color: var(--accent);
  flex-shrink: 0;
}

.retrieval-count {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.source-count {
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  color: var(--accent);
}

.show-all-btn {
  padding: 4px 12px;
  font-size: 11px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.show-all-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.show-all-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.2);
}

.collapse-btn {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.collapse-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.2);
}

.collapse-icon {
  font-size: 10px;
  line-height: 1;
  display: inline-flex;
  transition: transform 0.2s ease;
}

.collapse-icon svg {
  width: 10px;
  height: 10px;
}

.collapse-icon.is-open {
  transform: rotate(180deg);
}

.chunks-scroll {
  max-height: 320px;
  overflow: auto;
  padding-right: 2px;
}

.chunks-scroll::-webkit-scrollbar {
  width: 8px;
}

.chunks-scroll::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 6px;
}

.chunks-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
  border-radius: 6px;
}

.chunks-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}

.chunks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.chunk-card {
  position: relative;
  padding: 10px;
  border-radius: 10px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
  overflow: hidden;
}

.chunk-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.chunk-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  opacity: 0;
  transition: opacity 0.2s;
}

.chunk-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
}

.chunk-card:hover::before {
  opacity: 1;
}

.chunk-card.score-high {
  border-left: 3px solid #22c55e;
}

.chunk-card.score-medium {
  border-left: 3px solid #eab308;
}

.chunk-card.score-low {
  border-left: 3px solid #6b7280;
}

.chunk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.rank-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  letter-spacing: 0.02em;
  line-height: 1.4;
}

.rank-1 {
  background: rgba(34, 197, 94, 0.14);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.rank-2 {
  background: rgba(234, 179, 8, 0.12);
  color: #eab308;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.rank-3 {
  background: rgba(129, 140, 248, 0.12);
  color: var(--primary-container);
  border: 1px solid rgba(129, 140, 248, 0.3);
}

.rank-other {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.chunk-score {
  flex-shrink: 0;
}

.score-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  border-radius: 999px;
  min-width: 42px;
}

.chunk-source {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.source-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-page {
  font-size: 10px;
  color: var(--text-muted);
}

.expand-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
  flex-shrink: 0;
}

.expand-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.expand-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
}

.expand-chevron {
  display: inline-flex;
  transition: transform 0.2s ease;
}

.expand-chevron svg {
  width: 10px;
  height: 10px;
}

.expand-chevron.is-open {
  transform: rotate(180deg);
}

.copy-chunk-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s, opacity 0.2s;
  flex-shrink: 0;
  opacity: 0;
}

.copy-chunk-btn svg {
  width: 12px;
  height: 12px;
}

.chunk-card:hover .copy-chunk-btn,
.copy-chunk-btn:focus-visible {
  opacity: 1;
}

.copy-chunk-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  color: var(--accent);
  border-color: rgba(99, 102, 241, 0.4);
}

.chunk-progress {
  height: 3px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-bar {
  height: 100%;
  transition: width 0.5s ease;
  border-radius: 2px;
}

.chunk-content {
  margin-bottom: 8px;
}

.chunk-preview {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-main);
  margin: 0;
  padding: 8px;
  background: var(--surface-container-low);
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.chunk-preview::-webkit-scrollbar {
  width: 6px;
}

.chunk-preview::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.chunk-preview::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.chunk-preview::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.chunk-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
}

.view-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.2s;
}

.view-hint svg {
  width: 12px;
  height: 12px;
}

.chunk-card:hover .view-hint {
  opacity: 1;
}

.char-count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  white-space: nowrap;
}

.chunk-preview :deep(.kw-hit) {
  background: rgba(129, 140, 248, 0.28);
  border-radius: 2px;
  padding: 0 1px;
  color: inherit;
}

/* Teleported tooltip styles (outside scoped context) */
.chunk-tooltip {
  position: fixed;
  z-index: 5000;
  min-width: 300px;
  max-width: 450px;
  background: var(--surface-container-high);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
  padding: 12px;
  pointer-events: none;
  animation: chunkTooltipFadeIn 0.2s ease;
}

@keyframes chunkTooltipFadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

.chunk-tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--outline-variant);
}

.chunk-tooltip-header .tooltip-source {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.tooltip-file-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: var(--accent);
}

.chunk-tooltip-header .tooltip-page {
  font-size: 10px;
  color: var(--text-muted);
}

.chunk-tooltip-header .tooltip-score {
  margin-left: auto;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.15);
}

.chunk-tooltip-body {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-main);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
