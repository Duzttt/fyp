<script setup>
import { ref, shallowRef, onUnmounted, watch } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.js?url'

// Use a locally bundled worker instead of a CDN so the viewer
// works offline and never hangs waiting for an external script.
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  pdfUrl: {
    type: String,
    default: '',
  },
  targetPage: {
    type: Number,
    default: 1,
  },
  highlightText: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'page-change'])

const currentPage = ref(1)
const totalPages = ref(0)
// shallowRef: pdf.js document/canvas are class instances (private fields) or DOM
// nodes — deep reactive proxying breaks them ("Cannot read from private field").
const pdfDoc = shallowRef(null)
const canvas = shallowRef(null)
const isLoading = ref(false)
const error = ref('')
const scale = ref(1.5)

let currentLoadingTask = null
let loadTimeoutId = null
let renderToken = 0
let activeLoadId = 0

onUnmounted(() => {
  clearTimeout(loadTimeoutId)
  if (currentLoadingTask) {
    currentLoadingTask.destroy()
    currentLoadingTask = null
  }
  if (pdfDoc.value) {
    pdfDoc.value.destroy()
    pdfDoc.value = null
  }
})

const loadPdf = async () => {
  if (!props.pdfUrl) return

  const loadId = ++activeLoadId

  if (currentLoadingTask) {
    const stale = currentLoadingTask
    currentLoadingTask = null
    stale.destroy()
  }

  clearTimeout(loadTimeoutId)
  isLoading.value = true
  error.value = ''

  const loadingTask = pdfjsLib.getDocument({
    url: props.pdfUrl,
    useWorkerFetch: false,
  })
  currentLoadingTask = loadingTask

  // Timeout guard: never leave the panel stuck on "Loading…"
  loadTimeoutId = setTimeout(() => {
    if (loadId !== activeLoadId) return
    loadingTask.destroy()
    if (currentLoadingTask === loadingTask) {
      currentLoadingTask = null
    }
    isLoading.value = false
    error.value = 'PDF load timed out. The file may be unavailable.'
  }, 30000)

  try {
    pdfDoc.value = await loadingTask.promise
    if (loadId !== activeLoadId) return
    totalPages.value = pdfDoc.value.numPages
    currentPage.value = props.targetPage || 1
    await renderPage(currentPage.value)
  } catch (err) {
    // A superseded load (stale task destroyed) is expected — stay silent.
    if (loadId !== activeLoadId) return
    if (err?.name !== 'AbortException' && !String(err?.message || '').includes('timed out')) {
      console.error('Failed to load PDF:', err)
      error.value = 'Failed to load PDF: ' + err.message
    }
  } finally {
    if (loadId !== activeLoadId) return
    clearTimeout(loadTimeoutId)
    if (currentLoadingTask === loadingTask) {
      currentLoadingTask = null
    }
    isLoading.value = false
  }
}

const renderPage = async (pageNum) => {
  if (!pdfDoc.value || !canvas.value) return

  const token = ++renderToken
  try {
    const page = await pdfDoc.value.getPage(pageNum)
    if (token !== renderToken) return
    const viewport = page.getViewport({ scale: scale.value })

    const ctx = canvas.value.getContext('2d')
    canvas.value.height = viewport.height
    canvas.value.width = viewport.width

    await page.render({
      canvasContext: ctx,
      viewport: viewport,
    }).promise
    if (token !== renderToken) return

    // Highlight text if provided
    if (props.highlightText) {
      await highlightTextOnPage(page, props.highlightText)
    }

    emit('page-change', pageNum)
  } catch (err) {
    console.error('Failed to render page:', err)
    error.value = 'Failed to render page: ' + err.message
  }
}

const highlightTextOnPage = async (page, text) => {
  // Get text content and find matches
  const textContent = await page.getTextContent()
  const viewport = page.getViewport({ scale: scale.value })

  // Simple text search - find matching text items
  const textItems = textContent.items.filter((item) => item.str)
  const query = text.toLowerCase()
  const ctx = canvas.value.getContext('2d')

  for (const item of textItems) {
    if (item.str.toLowerCase().includes(query)) {
      // Get position and draw highlight (viewport is already scaled)
      const transform = item.transform
      const x = transform[4] * scale.value
      const y = viewport.height - transform[5] * scale.value
      const width = item.width * scale.value
      const height = item.height * scale.value

      ctx.fillStyle = 'rgba(255, 255, 0, 0.4)'
      ctx.fillRect(x, y - height, width, height)
    }
  }
}

const previousPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    renderPage(currentPage.value)
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    renderPage(currentPage.value)
  }
}

const zoomIn = () => {
  scale.value = Math.min(scale.value + 0.25, 3)
  renderPage(currentPage.value)
}

const zoomOut = () => {
  scale.value = Math.max(scale.value - 0.25, 0.5)
  renderPage(currentPage.value)
}

// Load when the panel becomes visible with a URL, or when the URL changes
// while visible. A single watcher prevents double loads (URL + show).
watch(
  () => [props.show, props.pdfUrl],
  ([show, url], [prevShow, prevUrl]) => {
    const urlChanged = url !== prevUrl
    const becameVisible = show && !prevShow
    if (show && url && (urlChanged || becameVisible)) {
      loadPdf()
    }
  }
)
</script>

<template>
  <div v-if="show" class="pdf-viewer-panel" :class="{ visible: show }">
    <div class="pdf-viewer-header">
      <div class="pdf-viewer-title">
        <span>📄</span>
        <span>{{ pdfUrl ? pdfUrl.split('/').pop() : 'PDF Viewer' }}</span>
      </div>
      <div class="pdf-viewer-actions">
        <button type="button" class="pdf-viewer-btn" aria-label="Zoom out" @click="zoomOut">−</button>
        <button type="button" class="pdf-viewer-btn" aria-label="Zoom in" @click="zoomIn">+</button>
        <button type="button" class="pdf-viewer-btn" aria-label="Close PDF viewer" @click="$emit('close')">✕</button>
      </div>
    </div>

    <div class="pdf-viewer-nav">
      <button type="button" class="pdf-viewer-nav-btn" aria-label="Previous page" @click="previousPage" :disabled="currentPage <= 1">◀</button>
      <div class="pdf-viewer-page-info">
        Page <span class="current-page">{{ currentPage }}</span> of {{ totalPages || '—' }}
      </div>
      <button type="button" class="pdf-viewer-nav-btn" aria-label="Next page" @click="nextPage" :disabled="currentPage >= totalPages">▶</button>
    </div>

    <div class="pdf-viewer-body" id="pdfViewerBody">
      <div class="pdf-canvas-container" v-show="!isLoading && !error">
        <canvas ref="canvas" id="pdfCanvas"></canvas>
      </div>

      <div v-if="isLoading" class="pdf-loading">
        <div class="pdf-loading-spinner"></div>
        <span>Loading PDF…</span>
      </div>

      <div v-else-if="error" class="pdf-error">
        <span>⚠️</span>
        <span>{{ error }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer-panel {
  position: fixed;
  top: max(80px, env(safe-area-inset-top, 0px));
  right: max(20px, env(safe-area-inset-right, 0px));
  width: 450px;
  max-width: calc(100vw - 40px - env(safe-area-inset-left, 0px) - env(safe-area-inset-right, 0px));
  height: calc(100vh - 100px - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px));
  background: var(--surface-container-high);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  z-index: 4000;
  overflow: hidden;
  overscroll-behavior: contain;
  display: none;
  flex-direction: column;
}

.pdf-viewer-panel.visible {
  display: flex;
}

.pdf-viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.15);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
  flex-shrink: 0;
}

.pdf-viewer-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-viewer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pdf-viewer-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.pdf-viewer-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.pdf-viewer-btn:hover {
  background: rgba(128, 128, 128, 0.2);
  color: var(--text-main);
}

.pdf-viewer-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--surface-container);
  border-bottom: 1px solid var(--outline-variant);
  flex-shrink: 0;
}

.pdf-viewer-nav-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.pdf-viewer-nav-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.pdf-viewer-nav-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.3);
  border-color: var(--accent);
}

.pdf-viewer-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.pdf-viewer-page-info {
  font-size: 12px;
  color: var(--text-muted);
}

.pdf-viewer-page-info .current-page {
  color: var(--accent);
  font-weight: 600;
}

.pdf-viewer-body {
  flex: 1;
  overflow: auto;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.pdf-canvas-container {
  position: relative;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  border-radius: 4px;
  overflow: hidden;
  max-width: 100%;
}

#pdfCanvas {
  display: block;
  max-width: 100%;
  height: auto;
}

.pdf-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
  gap: 12px;
}

.pdf-loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #fca5a5;
  gap: 12px;
  text-align: center;
  font-size: 12px;
}
</style>
