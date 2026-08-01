<script setup>
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip
} from 'chart.js'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  createABTest,
  debugRetrieval,
  deleteAdminDocument,
  generateReport,
  getABTestResults,
  getABTests,
  getAdminChunkQuality,
  getAdminDocumentAnalytics,
  getAdminDocumentChunks,
  getAdminDocuments,
  getAdminEmbeddingVisualization,
  getAdminIndexingStatus,
  getAdminQueryClusters,
  getAdminQueryStats,
  getAdminStats,
  getHealthScore,
  getReportsHistory,
  getUserBehavior,
  reindexAdminDocument,
  startABTest,
  stopABTest,
  traceRetrieval
} from '../../services/api'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const emit = defineEmits(['close'])

const activeTab = ref('overview')
const loading = ref(true)

// Stats data
const stats = ref({
  documents: { total: 0, chunks: 0, pages: 0 },
  vectors: { dimension: 384, count: 0, index_type: 'IndexFlatL2' },
  storage: { faiss_size_kb: 0, docs_size_kb: 0 },
  queries: { today: 0, week: 0, avg_latency_ms: 0, p95_latency_ms: 0, cache_hit_rate: 0 },
  health: { faiss_index: 'unknown', llm_service: 'unknown', disk_space: 'unknown', memory: 'unknown' }
})

// Query stats
const queryStats = ref({ total_queries: 0, avg_latency_ms: 0, type_distribution: [] })

// Retrieval debug
const debugQuery = ref('')
const debugParams = ref({
  alpha: 0.3,
  fusion: 'rrf',
  top_k: 5,
  rrf_k: 60
})
const debugResults = ref(null)
const debugLoading = ref(false)

// Documents
const documents = ref([])
const documentsLoading = ref(false)
const documentSearch = ref('')
const chunkSearch = ref('')
const actionDocId = ref(null)
const selectedDoc = ref(null)
const documentChunks = ref([])
const chunksLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalChunks = ref(0)

// Indexing status
const indexingStatus = ref({ status: 'idle', progress: 0, current_file: '' })

// Phase 2: Analytics data
const selectedDocForAnalytics = ref(null)
const selectedDocForAnalyticsId = ref('')
const docAnalytics = ref(null)
const docAnalyticsLoading = ref(false)
const queryClusters = ref({ clusters: [], total_queries: 0 })
const embeddingViz = ref({ points: [], documents: [] })
const chunkQuality = ref({ top_chunks: [], low_quality_chunks: [], overall_score: 0 })
const traceResults = ref(null)
const abTests = ref([])

// Phase 3: Smart Operations data
const userBehavior = ref({ active_users: 0, segments: [], user_paths: [] })
const reportsHistory = ref([])
const healthScore = ref({ overall_score: 0, dimensions: {}, issues: [] })

// Notifications system
const notifications = ref([])
let notifId = 0
const notify = (message, type = 'info') => {
  const id = ++notifId
  notifications.value.push({ id, message, type })
  setTimeout(() => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }, 4000)
}
const dismissNotif = (id) => {
  notifications.value = notifications.value.filter(n => n.id !== id)
}
const confirmAction = (message) => {
  return window.confirm(message)
}

const embeddingBounds = computed(() => {
  const points = embeddingViz.value.points || []
  if (points.length === 0) return { minX: 0, maxX: 1, minY: 0, maxY: 1, xRange: 1, yRange: 1 }
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  return { minX, maxX, minY, maxY, xRange: maxX - minX || 1, yRange: maxY - minY || 1 }
})

let searchDebounceTimer = null
const debouncedLoadDocuments = () => {
  clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(loadDocuments, 300)
}

// Phase 3: Form data
const reportForm = ref({
  type: 'daily',
  sections: ['overview', 'performance'],
})
const abTestResults = ref(null)

// Phase 2: Loading states
const analyticsLoading = ref(false)
const vizMethod = ref('pca')
const hoveredPoint = ref(null)
const selectedPoint = ref(null)
const highlightDoc = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })

const legendColor = (doc) => {
  const p = (embeddingViz.value.points || []).find(p => p.document === doc)
  return p?.document_color || '#888'
}

const onVizMouseMove = (e) => {
  tooltipPos.value = { x: e.offsetX, y: e.offsetY }
}

const toggleHighlight = (doc) => {
  highlightDoc.value = highlightDoc.value === doc ? null : doc
}
const traceQuery = ref('')
const traceLoading = ref(false)

// New test form
const newTestForm = ref({
  name: '',
  description: '',
  traffic_split: [50, 50],
  variants: [
    { name: 'control', config: { top_k: 3, temperature: 0.7, similarity_threshold: 0.6, reranker_enabled: false } },
    { name: 'variant_a', config: { top_k: 5, temperature: 0.9, similarity_threshold: 0.5, reranker_enabled: true } },
  ],
})

const addVariant = () => {
  newTestForm.value.variants.push({ name: 'variant_' + newTestForm.value.variants.length, config: { top_k: 3, temperature: 0.7, similarity_threshold: 0.6, reranker_enabled: false } })
  newTestForm.value.traffic_split.push(0)
}

const removeVariant = (index) => {
  newTestForm.value.variants.splice(index, 1)
  newTestForm.value.traffic_split.splice(index, 1)
}

const variantConfigText = (config) => {
  const c = config || {}
  const parts = []
  if (c.top_k != null) parts.push('top_k=' + c.top_k)
  if (c.temperature != null) parts.push('temp=' + c.temperature)
  if (c.similarity_threshold != null) parts.push('sim=' + c.similarity_threshold)
  if (c.reranker_enabled != null) parts.push('reranker=' + (c.reranker_enabled ? 'on' : 'off'))
  return parts.join(' · ') || '(default config)'
}

const tabGroups = [
  {
    label: 'System',
    items: [
      {
        id: 'overview',
        label: 'Overview',
        icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
      },
    ],
  },
  {
    label: 'Retrieval',
    items: [
      {
        id: 'retrieval',
        label: 'Retrieval Debug',
        icon: 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
      },
      {
        id: 'clusters',
        label: 'Query Clusters',
        icon: 'M12 8c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm8 12c0-2.21-1.79-4-4-4H8c-2.21 0-4 1.79-4 4v2h16v-2zM4 16.5V15c0-1.1.9-2 2-2h12c1.1 0 2 .9 2 2v1.5a6 6 0 0 0-16 0z',
      },
      {
        id: 'viz',
        label: 'Vector Viz',
        icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
      },
      {
        id: 'quality',
        label: 'Chunk Quality',
        icon: 'M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z',
      },
    ],
  },
  {
    label: 'Documents',
    items: [
      {
        id: 'documents',
        label: 'Documents',
        icon: 'M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
      },
      {
        id: 'analytics',
        label: 'Analytics',
        icon: 'M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z',
      },
    ],
  },
  {
    label: 'Research',
    items: [
      {
        id: 'abtest',
        label: 'A/B Test',
        icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5v-4.58l.99.99 4-4 4 4 4-4 4.01 4.01V19z',
      },
      {
        id: 'users',
        label: 'Users',
        icon: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z',
      },
      {
        id: 'reports',
        label: 'Reports',
        icon: 'M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM8 17H6v-2h2v2zm0-4H6v-2h2v2zm0-4H6V7h2v2zm6 8h-4v-2h4v2zm0-4h-4v-2h4v2zm-1-5V3.5L18.5 9H13z',
      },
    ],
  },
]

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#9ca3af' } }
  },
  scales: {
    x: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
    y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } }
  }
}))

const loadStats = async () => {
  try {
    const data = await getAdminStats()
    stats.value = data
  } catch (err) {
    console.error('Failed to load stats:', err)
  }
}

const loadQueryStats = async () => {
  try {
    const data = await getAdminQueryStats(24)
    queryStats.value = data
  } catch (err) {
    console.error('Failed to load query stats:', err)
  }
}

const loadDocuments = async () => {
  documentsLoading.value = true
  try {
    const data = await getAdminDocuments(documentSearch.value)
    documents.value = data.documents
  } catch (err) {
    console.error('Failed to load documents:', err)
  } finally {
    documentsLoading.value = false
  }
}

const loadChunks = async (docId, page = 1, search = '') => {
  chunksLoading.value = true
  currentPage.value = page
  try {
    const data = await getAdminDocumentChunks(docId, page, pageSize.value, search)
    documentChunks.value = data.chunks
    totalChunks.value = data.total
  } catch (err) {
    console.error('Failed to load chunks:', err)
  } finally {
    chunksLoading.value = false
  }
}

let chunkSearchDebounceTimer = null
const debouncedLoadChunks = () => {
  clearTimeout(chunkSearchDebounceTimer)
  chunkSearchDebounceTimer = setTimeout(() => {
    if (selectedDoc.value) {
      currentPage.value = 1
      loadChunks(selectedDoc.value.id, 1, chunkSearch.value)
    }
  }, 300)
}

const handleDebugSearch = async () => {
  if (!debugQuery.value.trim()) return
  
  debugLoading.value = true
  debugResults.value = null
  try {
    const data = await debugRetrieval(debugQuery.value, debugParams.value)
    debugResults.value = data
  } catch (err) {
    console.error('Debug retrieval failed:', err)
    notify('Debug retrieval failed: ' + err.message, 'error')
  } finally {
    debugLoading.value = false
  }
}

const handleDeleteDocument = async (docId) => {
  if (!confirmAction(`Delete document "${docId}"? This will rebuild the index.`)) return

  actionDocId.value = docId
  try {
    await deleteAdminDocument(docId)
    notify('Document deleted successfully', 'success')
    await loadDocuments()
  } catch (err) {
    notify('Failed to delete document: ' + err.message, 'error')
  } finally {
    actionDocId.value = null
  }
}

const handleReindexDocument = async (docId) => {
  actionDocId.value = docId
  try {
    await reindexAdminDocument(docId)
    notify('Document reindexed successfully', 'success')
  } catch (err) {
    notify('Failed to reindex document: ' + err.message, 'error')
  } finally {
    actionDocId.value = null
  }
}

const handleViewChunks = (doc) => {
  selectedDoc.value = doc
  loadChunks(doc.id, 1)
}

const handleViewDocAnalytics = async (doc) => {
  selectedDocForAnalytics.value = doc
  selectedDocForAnalyticsId.value = doc.id
  await loadDocumentAnalytics(doc.id)
  activeTab.value = 'analytics'
}

const handleDocAnalyticsSelect = async (docId) => {
  const doc = documents.value.find(d => d.id === docId)
  if (!doc) return
  selectedDocForAnalytics.value = doc
  selectedDocForAnalyticsId.value = docId
  await loadDocumentAnalytics(docId)
}

const handleCloseChunks = () => {
  selectedDoc.value = null
  documentChunks.value = []
}

const formatSize = (kb) => {
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

const getHealthColor = (status) => {
  switch (status) {
    case 'healthy': return '#22c55e'
    case 'warning': return '#fbbf24'
    case 'empty': return '#f97316'
    default: return '#6b7280'
  }
}

// Query type distribution bar helpers
const maxTypeCount = computed(() =>
  Math.max(...(queryStats.value.type_distribution || []).map(item => item.count), 1)
)

const typeBarWidth = (item) => `${Math.round((item.count / maxTypeCount.value) * 100)}%`

const typeColor = (index) => {
  const colors = ['#818cf8', '#a855f7', '#22c55e', '#f59e0b', '#ec4899', '#06b6d4', '#f97316', '#ef4444']
  return colors[index % colors.length]
}

// Success rate display (null when no query logs exist yet)
const successRate = computed(() => {
  const rate = stats.value.queries?.success_rate
  return rate === null || rate === undefined ? null : rate
})

const successRateText = computed(() =>
  successRate.value === null ? '—' : `${successRate.value}%`
)

const successRateSub = computed(() =>
  successRate.value === null ? 'No queries in the last 7 days' : '7-day average'
)

// Latency display (— when no query logs exist yet)
const queryCount = computed(() => stats.value.queries?.query_count || 0)

const avgLatencyText = computed(() =>
  queryCount.value > 0 ? `${stats.value.queries.avg_latency_ms}ms` : '—'
)

const latencySub = computed(() =>
  queryCount.value > 0
    ? `P95: ${stats.value.queries.p95_latency_ms}ms · ${queryCount.value} queries`
    : 'No queries in the last 7 days'
)

const loadIndexingStatus = async () => {
  try {
    const data = await getAdminIndexingStatus()
    indexingStatus.value = data
  } catch (err) {
    console.error('Failed to load indexing status:', err)
  }
}

// Phase 2: Analytics functions
const loadDocumentAnalytics = async (docId) => {
  docAnalyticsLoading.value = true
  docAnalytics.value = null
  try {
    const data = await getAdminDocumentAnalytics(docId)
    docAnalytics.value = data
  } catch (err) {
    console.error('Failed to load document analytics:', err)
    docAnalytics.value = {
      retrieval_stats: { appearance_count: 0, avg_score: 0, click_count: 0, click_rate: 0 },
      top_queries: [],
      error: err?.response?.data?.detail || err.message || 'Failed to load document analytics',
    }
  } finally {
    docAnalyticsLoading.value = false
  }
}

const loadQueryClusters = async () => {
  analyticsLoading.value = true
  try {
    const data = await getAdminQueryClusters(30, 1000)
    queryClusters.value = data
  } catch (err) {
    console.error('Failed to load query clusters:', err)
    queryClusters.value = {
      clusters: [],
      total_queries: 0,
      message: err?.response?.data?.detail || err.message || 'Failed to load cluster data',
    }
  } finally {
    analyticsLoading.value = false
  }
}

const loadEmbeddingViz = async () => {
  analyticsLoading.value = true
  try {
    const data = await getAdminEmbeddingVisualization(vizMethod.value, 30, 500)
    embeddingViz.value = data
  } catch (err) {
    console.error('Failed to load embedding viz:', err)
    embeddingViz.value = {
      points: [],
      documents: [],
      error: err?.response?.data?.detail || err.message || 'Failed to load visualization',
    }
  } finally {
    analyticsLoading.value = false
  }
}

const loadChunkQuality = async () => {
  analyticsLoading.value = true
  try {
    const data = await getAdminChunkQuality()
    chunkQuality.value = data
  } catch (err) {
    console.error('Failed to load chunk quality:', err)
    chunkQuality.value = {
      top_chunks: [],
      low_quality_chunks: [],
      overall_score: 0,
      error: err?.response?.data?.detail || err.message || 'Failed to load chunk quality',
    }
  } finally {
    analyticsLoading.value = false
  }
}

const handleTrace = async () => {
  if (!traceQuery.value.trim()) return
  traceLoading.value = true
  try {
    const data = await traceRetrieval(traceQuery.value, 5)
    traceResults.value = data
  } catch (err) {
    console.error('Trace failed:', err)
  } finally {
    traceLoading.value = false
  }
}

const loadABTests = async () => {
  try {
    const data = await getABTests()
    abTests.value = data.tests || []
  } catch (err) {
    console.error('Failed to load AB tests:', err)
  }
}

const handleCreateTest = async () => {
  try {
    await createABTest(newTestForm.value)
    await loadABTests()
    newTestForm.value = {
      name: '',
      description: '',
      traffic_split: [50, 50],
      variants: [
        { name: 'control', config: { top_k: 3, temperature: 0.7, similarity_threshold: 0.6, reranker_enabled: false } },
        { name: 'variant_a', config: { top_k: 5, temperature: 0.9, similarity_threshold: 0.5, reranker_enabled: true } },
      ],
    }
    notify('Test created!', 'success')
  } catch (err) {
    notify('Failed to create test: ' + err.message, 'error')
  }
}

const handleStartTest = async (testId) => {
  try {
    await startABTest(testId)
    await loadABTests()
  } catch (err) {
    notify('Failed to start test: ' + err.message, 'error')
  }
}

const handleStopTest = async (testId) => {
  try {
    await stopABTest(testId)
    await loadABTests()
  } catch (err) {
    notify('Failed to stop test: ' + err.message, 'error')
  }
}

const handleViewResults = async (testId) => {
  try {
    const data = await getABTestResults(testId)
    abTestResults.value = data
  } catch (err) {
    console.error('Failed to load results:', err)
  }
}

const loadUserBehavior = async () => {
  try {
    const data = await getUserBehavior(7)
    userBehavior.value = data
  } catch (err) {
    console.error('Failed to load user behavior:', err)
  }
}

const loadReports = async () => {
  try {
    const data = await getReportsHistory()
    reportsHistory.value = data.reports || []
  } catch (err) {
    console.error('Failed to load reports:', err)
  }
}

const loadHealthScore = async () => {
  try {
    const data = await getHealthScore()
    healthScore.value = data
  } catch (err) {
    console.error('Failed to load health score:', err)
  }
}

const handleGenerateReport = async () => {
  try {
    const data = await generateReport(reportForm.value)
    notify('Report generated!', 'success')
    await loadReports()
  } catch (err) {
    notify('Failed to generate report: ' + err.message, 'error')
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadStats(), loadQueryStats(), loadDocuments(), loadIndexingStatus(), loadABTests(), loadUserBehavior(), loadReports(), loadHealthScore(), loadQueryClusters(), loadEmbeddingViz(), loadChunkQuality()])
  loading.value = false

  // Poll indexing status
  indexingInterval = setInterval(loadIndexingStatus, 3000)
})

let indexingInterval = null

onBeforeUnmount(() => {
  if (indexingInterval) clearInterval(indexingInterval)
})
</script>

<template>
  <div class="admin-panel">
    <div class="notif-container" v-if="notifications.length">
      <div
        v-for="n in notifications"
        :key="n.id"
        class="notif-toast"
        :class="'notif-' + n.type"
        @click="dismissNotif(n.id)"
      >
        <span>{{ n.message }}</span>
        <button type="button" class="notif-dismiss" aria-label="Dismiss">&times;</button>
      </div>
    </div>
    <div class="admin-header">
      <div class="admin-title">
        <span class="title-icon">🛠️</span>
        <span>Admin Dashboard</span>
      </div>
      <div class="admin-actions">
        <span class="status-badge" :class="indexingStatus.status">
          {{ indexingStatus.status === 'running' ? '⏳ Indexing...' : '✓ Ready' }}
        </span>
        <button class="close-btn" @click="emit('close')" aria-label="Close">✕</button>
      </div>
    </div>

    <!-- Tab Navigation -->
    <nav class="tab-nav">
      <div v-for="group in tabGroups" :key="group.label" class="tab-group">
        <span class="tab-group-label">{{ group.label }}</span>
        <div class="tab-group-items">
          <button
            v-for="tab in group.items"
            :key="tab.id"
            class="tab-btn"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            <svg class="tab-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path :d="tab.icon" />
            </svg>
            <span>{{ tab.label }}</span>
          </button>
        </div>
      </div>
    </nav>

    <div class="admin-content">
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <span>Loading...</span>
      </div>

      <!-- Overview Tab -->
      <div v-else-if="activeTab === 'overview'" class="tab-content">
        <!-- Stats Grid -->
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon docs">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.documents.total }}</div>
              <div class="stat-label">Documents</div>
              <div class="stat-sub">{{ stats.documents.chunks }} chunks · {{ stats.documents.pages }} pages</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon vectors">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4 6h2v2H4V6zm0 4h2v2H4v-2zm0 4h2v2H4v-2zm4-8h2v2H8V6zm0 4h2v2H8v-2zm0 4h2v2H8v-2zm4-8h2v2h-2V6zm0 4h2v2h-2v-2zm0 4h2v2h-2v-2zM16 6h2v2h-2V6zm0 4h2v2h-2v-2zm0 4h2v2h-2v-2z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.vectors.count.toLocaleString() }}</div>
              <div class="stat-label">Vectors</div>
              <div class="stat-sub">{{ stats.vectors.index_type }} · {{ stats.vectors.dimension }}D</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon queries">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 3.03-1.69 5.67-4.19 7.02l1.4 1.42A10.95 10.95 0 0 0 22 12c0-5.19-3.95-9.45-9-9.95zM11 2.05C5.95 2.55 2 6.81 2 12c0 2.62 1.01 5.02 2.65 6.83l1.41-1.41A8.93 8.93 0 0 1 4 12c0-4.08 3.05-7.44 7-7.93v-2.02zM11 4v4h2V4c2.87.48 5 2.95 5 5.93 0 1.49-.55 2.86-1.46 3.92l2.03 2.03A7.94 7.94 0 0 0 20 9.93C20 6.19 17.22 3.15 13.55 2.4L11 4z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.queries.today }}</div>
              <div class="stat-label">Today's Queries</div>
              <div class="stat-sub">{{ stats.queries.week }} this week</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon latency">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ avgLatencyText }}</div>
              <div class="stat-label">Avg Latency</div>
              <div class="stat-sub">{{ latencySub }}</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon cache">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ successRateText }}</div>
              <div class="stat-label">Success Rate</div>
              <div class="stat-sub">{{ successRateSub }}</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon storage">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M2 20h20v-4H2v4zm2-3h2v2H4v-2zM2 4v4h20V4H2zm4 3H4V5h2v2zm-4 7h20v-4H2v4zm2-3h2v2H4v-2z" /></svg>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ formatSize(stats.storage.faiss_size_kb) }}</div>
              <div class="stat-label">Index Size</div>
              <div class="stat-sub">Docs: {{ formatSize(stats.storage.docs_size_kb) }}</div>
            </div>
          </div>
        </div>

        <!-- Quick Actions -->
        <div class="quick-actions">
          <button type="button" class="quick-action" @click="activeTab = 'retrieval'">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" /></svg>
            <span>Retrieval Debug</span>
          </button>
          <button type="button" class="quick-action" @click="activeTab = 'documents'">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" /></svg>
            <span>Documents</span>
          </button>
          <button type="button" class="quick-action" @click="activeTab = 'quality'">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
            <span>Chunk Quality</span>
          </button>
          <button type="button" class="quick-action" @click="activeTab = 'alerts'">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" /></svg>
            <span>Alerts</span>
          </button>
          <button type="button" class="quick-action" @click="activeTab = 'viz'">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>
            <span>Vector Viz</span>
          </button>
        </div>

        <!-- Indexing Status Banner -->
        <div class="indexing-banner" :class="indexingStatus.status">
          <div class="banner-icon">
            <svg v-if="indexingStatus.status === 'running'" class="spin" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
            </svg>
          </div>
          <div class="banner-body">
            <span class="banner-title">
              {{ indexingStatus.status === 'running' ? 'Indexing in progress' : 'Index is ready' }}
            </span>
            <span v-if="indexingStatus.current_file" class="banner-sub">{{ indexingStatus.current_file }}</span>
            <span v-else class="banner-sub">
              {{ stats.documents.total }} documents · {{ stats.vectors.count.toLocaleString() }} vectors
            </span>
          </div>
          <div v-if="indexingStatus.status === 'running'" class="banner-progress">
            <div class="banner-progress-track">
              <div class="banner-progress-fill" :style="{ width: (indexingStatus.progress || 0) + '%' }"></div>
            </div>
            <span class="banner-percent">{{ indexingStatus.progress || 0 }}%</span>
          </div>
        </div>

        <!-- Health Status -->
        <div class="health-section">
          <h3 class="section-title">System Health</h3>
          <div class="health-grid">
            <div class="health-item">
              <span class="health-dot" :style="{ background: getHealthColor(stats.health.faiss_index) }" aria-hidden="true"></span>
              <div class="health-item-body">
                <span class="health-label">FAISS Index</span>
                <span class="health-status" :style="{ color: getHealthColor(stats.health.faiss_index) }">
                  {{ stats.health.faiss_index }}
                </span>
              </div>
            </div>
            <div class="health-item">
              <span class="health-dot" :style="{ background: getHealthColor(stats.health.llm_service) }" aria-hidden="true"></span>
              <div class="health-item-body">
                <span class="health-label">LLM Service</span>
                <span class="health-status" :style="{ color: getHealthColor(stats.health.llm_service) }">
                  {{ stats.health.llm_service }}
                </span>
              </div>
            </div>
            <div class="health-item">
              <span class="health-dot" :style="{ background: getHealthColor(stats.health.disk_space) }" aria-hidden="true"></span>
              <div class="health-item-body">
                <span class="health-label">Disk Space</span>
                <span class="health-status" :style="{ color: getHealthColor(stats.health.disk_space) }">
                  {{ stats.health.disk_space }}
                </span>
              </div>
            </div>
            <div class="health-item">
              <span class="health-dot" :style="{ background: getHealthColor(stats.health.memory) }" aria-hidden="true"></span>
              <div class="health-item-body">
                <span class="health-label">Memory</span>
                <span class="health-status" :style="{ color: getHealthColor(stats.health.memory) }">
                  {{ stats.health.memory }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="healthScore.overall_score" class="health-score-card">
            <div class="health-score-main">
              <span class="score-big">{{ healthScore.overall_score }}</span>
              <span class="score-label">/ 100</span>
            </div>
            <div class="dimension-scores">
              <div v-for="(dim, key) in healthScore.dimensions" :key="key" class="dim-item">
                <span class="dim-name">{{ dim.label }}</span>
                <div class="dim-bar">
                  <div class="dim-bar-fill" :style="{ width: (dim.score ?? 0) + '%' }"></div>
                </div>
                <span class="dim-score">{{ dim.score ?? '—' }}</span>
              </div>
            </div>
            <div v-if="healthScore.issues?.length" class="health-issues">
              <span class="issues-label">Issues to address</span>
              <div v-for="issue in healthScore.issues" :key="issue.message" class="issue-item" :class="issue.priority">
                <span class="issue-priority">{{ issue.priority }}</span>
                <span class="issue-message">{{ issue.message }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Query Distribution -->
        <div class="query-section">
          <h3 class="section-title">Query Statistics (24h)</h3>
          <div class="query-stats">
            <div class="query-stat">
              <span class="query-value">{{ queryStats.total_queries }}</span>
              <span class="query-label">Total Queries</span>
            </div>
            <div class="query-stat">
              <span class="query-value">{{ queryStats.avg_latency_ms }}ms</span>
              <span class="query-label">Avg Latency</span>
            </div>
          </div>
          <div v-if="queryStats.type_distribution?.length" class="type-dist">
            <div
              v-for="(item, index) in queryStats.type_distribution"
              :key="item.query_type"
              class="type-item"
            >
              <span class="type-name">{{ item.query_type }}</span>
              <div class="type-track">
                <span
                  class="type-fill"
                  :style="{ width: typeBarWidth(item), background: typeColor(index) }"
                />
              </div>
              <span class="type-count">{{ item.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Retrieval Debug Tab -->
      <div v-else-if="activeTab === 'retrieval'" class="tab-content">
        <div class="debug-section">
          <div class="debug-input">
            <input
              v-model="debugQuery"
              type="text"
              placeholder="Enter test query..."
              class="query-input"
              @keyup.enter="handleDebugSearch"
            />
            <button class="search-btn" @click="handleDebugSearch" :disabled="debugLoading">
              {{ debugLoading ? 'Searching...' : 'Search' }}
            </button>
          </div>

          <div class="debug-params">
            <div class="param-group">
              <label>Top K</label>
              <input v-model.number="debugParams.top_k" type="number" min="1" max="20" />
            </div>
            <div class="param-group">
              <label>Alpha (dense weight)</label>
              <input v-model.number="debugParams.alpha" type="number" min="0" max="1" step="0.1" />
            </div>
            <div class="param-group">
              <label>Fusion Method</label>
              <select v-model="debugParams.fusion">
                <option value="rrf">RRF (Reciprocal Rank)</option>
                <option value="weighted">Weighted</option>
              </select>
            </div>
            <div class="param-group">
              <label>RRF K</label>
              <input v-model.number="debugParams.rrf_k" type="number" min="1" max="100" />
            </div>
          </div>

          <div v-if="debugResults" class="debug-results">
            <div class="result-section">
              <h4>BM25 <span class="time">{{ debugResults.bm25?.time_ms }}ms</span></h4>
              <div v-if="debugResults.bm25?.results?.length" class="result-list">
                <div v-for="(r, i) in debugResults.bm25?.results" :key="'bm25-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="result-empty">No BM25 results</div>
            </div>

            <div class="result-section">
              <h4>Dense (Vector) <span class="time">{{ debugResults.dense?.time_ms }}ms</span></h4>
              <div v-if="debugResults.dense?.results?.length" class="result-list">
                <div v-for="(r, i) in debugResults.dense?.results" :key="'dense-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="result-empty">No Dense results</div>
            </div>

            <div class="result-section">
              <h4>Hybrid <span class="time">{{ debugResults.hybrid?.time_ms }}ms ({{ debugResults.hybrid?.fusion_method }})</span></h4>
              <div v-if="debugResults.hybrid?.results?.length" class="result-list">
                <div v-for="(r, i) in debugResults.hybrid?.results" :key="'hybrid-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="result-empty">No Hybrid results</div>
            </div>
          </div>
        </div>

        <!-- Pipeline Trace (merged from Trace tab) -->
        <div class="trace-section">
          <div class="section-header">
            <h3>Pipeline Trace</h3>
            <span class="trace-hint">Inspect stage timings for a query</span>
          </div>
          <div class="trace-input">
            <input
              v-model="traceQuery"
              type="text"
              placeholder="Enter query to trace..."
              class="query-input"
              @keyup.enter="handleTrace"
            />
            <button class="search-btn" @click="handleTrace" :disabled="traceLoading">
              {{ traceLoading ? 'Tracing...' : 'Trace' }}
            </button>
          </div>

          <div v-if="traceResults" class="trace-results">
            <div class="trace-summary">
              <span class="total-time">{{ traceResults.total_time }}ms</span>
              <span class="bottleneck">Bottleneck: {{ traceResults.bottleneck }}</span>
            </div>

            <div v-for="stage in traceResults.stages" :key="stage.name" class="trace-stage">
              <div class="stage-header">
                <span class="stage-name">{{ stage.name }}</span>
                <span class="stage-time">{{ stage.time_ms }}ms</span>
              </div>
              <div v-if="stage.results" class="stage-results">
                <div v-for="(r, i) in stage.results.slice(0, 3)" :key="i" class="result-preview">
                  {{ r.source || r.id }}: {{ r.score }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Documents Tab -->
      <div v-else-if="activeTab === 'documents'" class="tab-content">
        <!-- Document List -->
        <div v-if="!selectedDoc" class="documents-section">
          <div class="docs-header">
            <h3 class="section-title">Indexed Documents</h3>
            <div class="docs-search">
              <input
                v-model="documentSearch"
                type="text"
                placeholder="Search documents..."
                class="search-input"
                @input="debouncedLoadDocuments"
              />
              <button class="refresh-btn" aria-label="Refresh documents" title="Refresh documents" @click="loadDocuments">↻</button>
            </div>
          </div>

          <div v-if="documentsLoading" class="loading-small">Loading...</div>
          
          <div v-else class="docs-list">
            <div v-for="doc in documents" :key="doc.id" class="doc-item">
              <div class="doc-info">
                <div class="doc-name">{{ doc.name }}</div>
                <div class="doc-meta">
                  {{ formatSize(doc.size_kb) }} · {{ doc.chunk_count }} chunks
                </div>
                <div class="doc-date">{{ new Date(doc.created_at).toLocaleString() }}</div>
              </div>
              <div class="doc-actions">
                <button class="action-btn view" @click="handleViewChunks(doc)">Chunks</button>
                <button class="action-btn analytics" @click="handleViewDocAnalytics(doc)">Analytics</button>
                <button class="action-btn reindex" :disabled="actionDocId === doc.id" @click="handleReindexDocument(doc.id)">
                  {{ actionDocId === doc.id ? 'Reindexing...' : 'Reindex' }}
                </button>
                <button class="action-btn delete" :disabled="actionDocId === doc.id" @click="handleDeleteDocument(doc.id)">
                  {{ actionDocId === doc.id ? 'Deleting...' : 'Delete' }}
                </button>
              </div>
            </div>
            
            <div v-if="documents.length === 0" class="empty-state">
              No documents found
            </div>
          </div>
        </div>

        <!-- Chunk Browser -->
        <div v-else class="chunks-section">
          <div class="chunks-header">
            <button class="back-btn" @click="handleCloseChunks">← Back</button>
            <h3 class="section-title">{{ selectedDoc.name }}</h3>
            <input
              v-model="chunkSearch"
              type="text"
              placeholder="Search chunks..."
              class="search-input chunk-search"
              @input="debouncedLoadChunks"
            />
            <span class="chunks-count">{{ totalChunks }} chunks</span>
          </div>

          <div v-if="chunksLoading" class="loading-small">Loading chunks...</div>
          
          <div v-else class="chunks-list">
            <div v-for="chunk in documentChunks" :key="chunk.index" class="chunk-item">
              <div class="chunk-header">
                <span class="chunk-index">#{{ chunk.index }}</span>
                <span v-if="chunk.page" class="chunk-page">Page {{ chunk.page }}</span>
              </div>
              <div class="chunk-text">{{ chunk.text }}</div>
            </div>
            <div v-if="documentChunks.length === 0" class="empty-state">No chunks found</div>
          </div>

          <!-- Pagination -->
          <div v-if="totalChunks > pageSize" class="pagination">
            <button
              :disabled="currentPage === 1"
              @click="loadChunks(selectedDoc.id, currentPage - 1)"
            >
              Previous
            </button>
            <span class="page-info">Page {{ currentPage }} of {{ Math.ceil(totalChunks / pageSize) }}</span>
            <button
              :disabled="currentPage >= Math.ceil(totalChunks / pageSize)"
              @click="loadChunks(selectedDoc.id, currentPage + 1)"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <!-- Analytics Tab -->
      <div v-else-if="activeTab === 'analytics'" class="tab-content">
        <div class="analytics-section">
          <div v-if="selectedDocForAnalytics" class="doc-analytics">
            <div class="section-header">
              <button class="back-btn" @click="selectedDocForAnalytics = null; selectedDocForAnalyticsId = ''">← Back</button>
              <h3>{{ selectedDocForAnalytics.name }}</h3>
            </div>
            
            <div v-if="docAnalyticsLoading" class="loading-small">Loading analytics...</div>
            <template v-else-if="docAnalytics">
              <div v-if="docAnalytics.error" class="quality-error">{{ docAnalytics.error }}</div>

              <div class="analytics-stats">
                <div class="stat-card">
                  <div class="stat-value">{{ docAnalytics.retrieval_stats.appearance_count }}</div>
                  <div class="stat-label">Appearance Count</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">{{ Number(docAnalytics.retrieval_stats.avg_score).toFixed(3) }}</div>
                  <div class="stat-label">Avg Score</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">{{ docAnalytics.retrieval_stats.click_count }}</div>
                  <div class="stat-label">Click Count</div>
                </div>
                <div class="stat-card">
                  <div class="stat-value">{{ (docAnalytics.retrieval_stats.click_rate * 100).toFixed(1) }}%</div>
                  <div class="stat-label">Click Rate</div>
                </div>
              </div>
              
              <div class="top-queries">
                <h4>Top Queries</h4>
                <div v-if="docAnalytics.top_queries?.length" class="query-list">
                  <div v-for="q in docAnalytics.top_queries" :key="q.query" class="query-item">
                    <span class="query-text">{{ q.query }}</span>
                    <span class="query-count">{{ q.count }} times</span>
                  </div>
                </div>
                <div v-else class="quality-empty">No query data for this document</div>
              </div>
            </template>
          </div>
          
          <div v-else class="select-doc">
            <h3>Select a Document</h3>
            <p>Choose a document to view its retrieval analytics</p>
            <select
              v-model="selectedDocForAnalyticsId"
              class="doc-select"
              @change="handleDocAnalyticsSelect(selectedDocForAnalyticsId)"
            >
              <option value="">Choose a document...</option>
              <option v-for="d in documents" :key="d.id" :value="d.id">
                {{ d.name }} ({{ d.chunk_count }} chunks)
              </option>
            </select>
            <button class="action-btn" @click="activeTab = 'documents'">Go to Documents</button>
          </div>
        </div>
      </div>

      <!-- Query Clusters Tab -->
      <div v-else-if="activeTab === 'clusters'" class="tab-content">
        <div class="clusters-section">
          <div class="section-header">
            <h3>Query Semantic Clusters</h3>
            <button class="refresh-btn" :disabled="analyticsLoading" aria-label="Refresh query clusters" title="Refresh query clusters" @click="loadQueryClusters">{{ analyticsLoading ? '⟳' : '↻' }}</button>
          </div>

          <div v-if="queryClusters.clusters?.length" class="clusters-list">
            <div class="clusters-summary">
              <span>{{ queryClusters.total_queries }} unique queries</span>
              <span v-if="queryClusters.days">· last {{ queryClusters.days }} days</span>
            </div>
            <div v-for="cluster in queryClusters.clusters" :key="cluster.name" class="cluster-item">
              <div class="cluster-header">
                <span class="cluster-color" :style="{ background: cluster.color }"></span>
                <span class="cluster-name">{{ cluster.name.replace('_', ' ') }}</span>
                <span class="cluster-count">{{ cluster.count }}</span>
                <span class="cluster-pct">{{ cluster.percentage }}%</span>
              </div>
              <div v-if="cluster.patterns?.length" class="cluster-patterns">
                <span v-for="p in cluster.patterns" :key="p" class="pattern-tag">{{ p }}</span>
              </div>
              <div v-if="cluster.sample_queries?.length" class="cluster-samples">
                <div v-for="(q, qi) in cluster.sample_queries" :key="qi" class="sample-query">
                  <span class="sample-index">{{ qi + 1 }}</span>
                  <span class="sample-text">{{ q }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">{{ queryClusters.message || 'No cluster data available' }}</div>
        </div>
      </div>
      <!-- Trace Tab -->
      <!-- A/B Test Tab -->
      <div v-else-if="activeTab === 'abtest'" class="tab-content">
        <div class="abtest-section">
          <div class="create-test">
            <h3>Create New A/B Test</h3>
            <p class="abtest-hint">
              While a test is <strong>running</strong>, chat requests are split by session
              (X-Session-Id) across variants, and each variant's config overrides
              top_k / temperature / similarity_threshold / reranker for that request.
            </p>
            <div class="form-group">
              <label>Test Name</label>
              <input v-model="newTestForm.name" type="text" placeholder="Test name..." />
            </div>
            <div class="form-group">
              <label>Description</label>
              <textarea v-model="newTestForm.description" placeholder="Description..."></textarea>
            </div>
            <div class="form-group">
              <label>Traffic Split (%)</label>
              <div class="split-inputs">
                <input
                  v-for="(v, i) in newTestForm.variants"
                  :key="i"
                  v-model.number="newTestForm.traffic_split[i]"
                  type="number"
                  min="0"
                  max="100"
                  :title="v.name"
                />
              </div>
            </div>
            <div class="form-group">
              <label>Variants</label>
              <div v-for="(v, i) in newTestForm.variants" :key="i" class="variant-editor">
                <div class="variant-name-row">
                  <input v-model="v.name" type="text" :placeholder="'Variant ' + (i + 1)" />
                  <button
                    v-if="newTestForm.variants.length > 2"
                    type="button"
                    class="action-btn delete"
                    @click="removeVariant(i)"
                  >✕</button>
                </div>
                <div class="variant-config">
                  <label>top_k</label>
                  <input v-model.number="v.config.top_k" type="number" min="1" max="20" />
                  <label>temp</label>
                  <input v-model.number="v.config.temperature" type="number" min="0" max="2" step="0.1" />
                  <label>sim</label>
                  <input v-model.number="v.config.similarity_threshold" type="number" min="0" max="1" step="0.05" />
                  <label class="checkbox-label">
                    <input v-model="v.config.reranker_enabled" type="checkbox" /> reranker
                  </label>
                </div>
              </div>
              <button type="button" class="action-btn" @click="addVariant">+ Add variant</button>
            </div>
            <button class="btn btn-primary" @click="handleCreateTest">Create Test</button>
          </div>
          
          <div class="tests-list">
            <h3>Existing Tests</h3>
            <div v-for="test in abTests" :key="test.id" class="test-item">
              <div class="test-info">
                <span class="test-name">{{ test.name }}</span>
                <span class="test-status" :class="test.status">{{ test.status }}</span>
              </div>
              <div v-if="test.variants?.length" class="test-variants">
                <div v-for="v in test.variants" :key="v.name" class="test-variant">
                  <span class="test-variant-name">{{ v.name }}</span>
                  <span class="test-variant-config">{{ variantConfigText(v.config) }}</span>
                </div>
              </div>
              <div class="test-actions">
                <button v-if="test.status === 'draft'" class="action-btn" @click="handleStartTest(test.id)">Start</button>
                <button v-if="test.status === 'running'" class="action-btn" @click="handleStopTest(test.id)">Stop</button>
                <button class="action-btn" @click="handleViewResults(test.id)">Results</button>
              </div>
            </div>
            <div v-if="!abTests.length" class="quality-empty">No tests yet — create one above</div>
          </div>
          
          <div v-if="abTestResults" class="results-modal">
            <h4>Test Results</h4>
            <div v-for="r in abTestResults.results" :key="r.variant" class="result-row">
              <span>{{ r.variant }}</span>
              <span>{{ r.samples }} samples</span>
              <span>Score: {{ r.avg_score }}</span>
              <span>Latency: {{ r.avg_latency_ms }}ms</span>
              <span>Feedback: {{ (r.positive_feedback_rate * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>
      <!-- Users Tab -->
      <div v-else-if="activeTab === 'users'" class="tab-content">
        <div class="users-section">
          <div class="section-header">
            <h3>👥 User Behavior</h3>
            <button class="refresh-btn" aria-label="Refresh user behavior metrics" title="Refresh user behavior metrics" @click="loadUserBehavior">↻</button>
          </div>
          
          <div class="user-stats">
            <div class="user-stat">
              <span class="user-value">{{ userBehavior.active_users || 0 }}</span>
              <span class="user-label">Active Users</span>
            </div>
            <div class="user-stat">
              <span class="user-value">{{ userBehavior.sessions?.avg_queries || 0 }}</span>
              <span class="user-label">Avg Queries/Session</span>
            </div>
          </div>
          
          <div class="user-segments">
            <h4>User Segments</h4>
            <div v-for="seg in userBehavior.segments" :key="seg.name" class="segment-item">
              <span class="seg-name">{{ seg.name }}</span>
              <span class="seg-pct">{{ seg.percentage }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Reports Tab -->
      <div v-else-if="activeTab === 'reports'" class="tab-content">
        <div class="reports-section">
          <div class="section-header">
            <h3>📑 Reports</h3>
          </div>
          
          <div class="report-form">
            <div class="form-group">
              <label>Report Type</label>
              <select v-model="reportForm.type">
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
            <button class="btn btn-primary" @click="handleGenerateReport">Generate Report</button>
          </div>
          
          <div class="reports-list">
            <h4>Recent Reports</h4>
            <div v-for="report in reportsHistory" :key="report.id" class="report-item">
              <span class="report-type">{{ report.type }}</span>
              <span class="report-date">{{ new Date(report.generated_at).toLocaleString() }}</span>
            </div>
            <div v-if="!reportsHistory.length" class="empty-state">No reports generated yet</div>
          </div>
        </div>
      </div>

      <!-- Health Tab -->
    </div>
  </div>
</template>

<style scoped>
.notif-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
}
.notif-toast {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
  animation: notifSlideIn 0.2s ease;
  backdrop-filter: blur(12px);
}
.notif-info { background: rgba(99, 102, 241, 0.9); }
.notif-success { background: rgba(34, 197, 94, 0.9); }
.notif-error { background: rgba(239, 68, 68, 0.9); }
.notif-dismiss {
  background: none;
  border: none;
  color: white;
  font-size: 18px;
  cursor: pointer;
  opacity: 0.7;
  flex-shrink: 0;
}
.notif-dismiss:hover { opacity: 1; }
@keyframes notifSlideIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
.admin-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(1100px, 95vw);
  height: min(850px, 90vh);
  background: var(--surface-container);
  backdrop-filter: blur(20px);
  border: 1px solid var(--primary-container);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  z-index: 6000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
}

.admin-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--on-surface);
}

.title-icon {
  font-size: 18px;
}

.admin-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge.running {
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.3);
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.close-btn:hover {
  background: var(--tertiary-container);
  border-color: var(--tertiary);
  color: var(--on-tertiary);
}

.tab-nav {
  display: flex;
  gap: 18px;
  padding: 8px 16px;
  background: var(--surface-container-low);
  border-bottom: 1px solid var(--outline-variant);
  overflow-x: auto;
  scrollbar-width: thin;
}

.tab-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.tab-group-label {
  padding: 0 8px;
  font-size: 10px;
  font-weight: 700;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  opacity: 0.75;
}

.tab-group-items {
  display: flex;
  gap: 4px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.tab-btn:hover {
  background: var(--surface-container-high);
  color: var(--on-surface);
}

.tab-btn.active {
  background: rgba(99, 102, 241, 0.14);
  border-color: var(--primary-container);
  color: var(--primary);
}

.tab-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

/* Quick actions (overview) */
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-action {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 14px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  color: var(--text-main);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.quick-action:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(99, 102, 241, 0.08);
}

.quick-action svg {
  width: 15px;
  height: 15px;
  color: var(--accent);
}

/* Health score card (overview) */
.health-score-card {
  margin-top: 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
}

.health-score-main {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 14px;
}

.health-score-main .score-big {
  font-size: 30px;
  font-weight: 800;
  color: var(--accent);
}

.health-score-main .score-label {
  font-size: 13px;
  color: var(--text-muted);
}

.health-score-card .issues-label {
  display: block;
  margin: 12px 0 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-main);
}

.trace-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 16px;
  color: var(--text-muted);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--primary-container);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tab-content {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  transition: border-color 0.15s, transform 0.15s;
}

.stat-card:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 20px;
  height: 20px;
}

.stat-icon.docs { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.stat-icon.vectors { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
.stat-icon.queries { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.stat-icon.latency { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.stat-icon.cache { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
.stat-icon.storage { background: rgba(6, 182, 212, 0.15); color: #06b6d4; }

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--on-surface);
}

.stat-label {
  font-size: 11px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
}

.stat-sub {
  font-size: 10px;
  color: var(--on-surface-variant);
  margin-top: 2px;
}

/* Indexing status banner */
.indexing-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  margin-bottom: 24px;
}

.indexing-banner.running {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.08);
}

.indexing-banner.error {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
}

.banner-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.indexing-banner.running .banner-icon {
  background: rgba(99, 102, 241, 0.15);
  color: var(--accent);
}

.indexing-banner.error .banner-icon {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.banner-icon svg {
  width: 18px;
  height: 18px;
}

.banner-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
}

.banner-sub {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
}

.banner-progress-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.banner-progress-fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  transition: width 0.3s ease;
}

.banner-percent {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

/* Health Section */
.health-section, .query-section {
  margin-bottom: 24px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.health-item-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.health-label {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.health-status {
  font-size: 14px;
  font-weight: 600;
  text-transform: capitalize;
}

/* Query Section */
.query-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.query-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
}

.query-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
}

.query-label {
  font-size: 11px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.type-dist {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.type-name {
  font-size: 12px;
  color: var(--on-surface-variant);
  text-transform: capitalize;
  min-width: 120px;
  flex-shrink: 0;
}

.type-track {
  flex: 1;
  height: 7px;
  border-radius: 4px;
  background: var(--surface-container-high);
  overflow: hidden;
}

.type-fill {
  display: block;
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.type-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-main);
  min-width: 32px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* Debug Section */
.debug-section {
  max-width: 900px;
}

.debug-input {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.query-input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--on-surface);
  font-size: 14px;
  outline: none;
}

.query-input:focus {
  border-color: var(--primary-container);
}

.search-btn {
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  color: var(--on-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.search-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.debug-params {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: var(--surface-container-high);
  border-radius: 12px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-group label {
  font-size: 11px;
  color: var(--on-surface-variant);
  text-transform: uppercase;
}

.param-group input,
.param-group select {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  outline: none;
}

.debug-results {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.result-section {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  padding: 16px;
}

.result-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.result-section .time {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-weight: normal;
  margin-left: 8px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.result-empty {
  padding: 24px 16px;
  border: 1px dashed var(--outline-variant);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.result-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: var(--surface-container);
  border-radius: 8px;
}

.result-rank {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-container);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--on-primary);
  flex-shrink: 0;
}

.result-content {
  flex: 1;
  min-width: 0;
}

.result-score {
  font-size: 11px;
  color: var(--tertiary);
  font-weight: 600;
}

.result-text {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-source {
  font-size: 10px;
  color: var(--on-surface-variant);
  margin-top: 4px;
  opacity: 0.7;
}

/* Documents Section */
.docs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.docs-search {
  display: flex;
  gap: 8px;
}

.search-input {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
  outline: none;
  width: 200px;
}

.refresh-btn {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-small {
  text-align: center;
  padding: 40px;
  color: var(--on-surface-variant);
}

.docs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
}

.doc-info {
  flex: 1;
}

.doc-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

.doc-meta {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-top: 2px;
}

.doc-date {
  font-size: 11px;
  color: var(--on-surface-variant);
  opacity: 0.7;
  margin-top: 2px;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--surface-container-highest);
  color: var(--on-surface);
}

.action-btn.delete:hover {
  background: var(--tertiary-container);
  border-color: var(--tertiary);
  color: var(--on-tertiary);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--on-surface-variant);
}

/* Chunks Section */
.chunks-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.back-btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  cursor: pointer;
}

.chunks-count {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-left: auto;
}

.chunk-search {
  max-width: 280px;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 12px;
  outline: none;
}

.chunk-search:focus {
  border-color: var(--accent);
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.chunk-item {
  padding: 14px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
}

.chunk-header {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.chunk-index {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-container);
}

.chunk-page {
  font-size: 11px;
  color: var(--on-surface-variant);
  background: var(--surface-container);
  padding: 2px 8px;
  border-radius: 4px;
}

.chunk-text {
  font-size: 13px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 20px;
}

.pagination button {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: var(--on-surface-variant);
}

/* Responsive */
@media (max-width: 800px) {
  .admin-panel {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
  }

  .debug-results {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: 1fr 1fr;
  }

  .health-grid {
    grid-template-columns: 1fr 1fr;
  }
}

/* Phase 2 Styles */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

/* Analytics Section */
.analytics-section {
  max-width: 800px;
}

.analytics-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.analytics-stats .stat-card {
  text-align: center;
}

.analytics-stats .stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--on-surface);
}

.analytics-stats .stat-label {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.top-queries {
  margin-top: 20px;
}

.top-queries h4 {
  font-size: 13px;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.query-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--surface-container-high);
  border-radius: 6px;
  margin-bottom: 6px;
}

.query-text {
  font-size: 13px;
  color: var(--on-surface-variant);
}

.query-count {
  font-size: 12px;
  color: var(--primary-container);
}

.select-doc {
  text-align: center;
  padding: 40px;
  color: var(--on-surface-variant);
}

.doc-select {
  display: block;
  margin: 16px auto;
  padding: 10px 14px;
  min-width: 320px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.doc-select:focus {
  border-color: var(--accent);
  outline: none;
}

/* Clusters Section */
.clusters-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cluster-item {
  padding: 16px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
}

.cluster-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.cluster-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.cluster-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
  text-transform: capitalize;
}

.cluster-pct {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-container);
  margin-left: auto;
}

.cluster-patterns {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.pattern-tag {
  font-size: 11px;
  padding: 3px 8px;
  background: var(--surface-container);
  border-radius: 4px;
  color: var(--on-surface-variant);
}

.clusters-summary {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-bottom: 4px;
}

.cluster-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface-variant);
  background: var(--surface-container);
  border-radius: 999px;
  padding: 2px 10px;
}

.cluster-samples {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.sample-query {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.sample-index {
  color: var(--primary-container);
  font-weight: 600;
  flex-shrink: 0;
}

.sample-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Failures Section */
.failure-rate {
  text-align: center;
  padding: 30px;
  background: var(--surface-container-high);
  border-radius: 12px;
  margin-bottom: 20px;
}

.rate-value {
  font-size: 48px;
  font-weight: 700;
  color: var(--tertiary);
}

.rate-label {
  display: block;
  font-size: 13px;
  color: var(--on-surface-variant);
  margin-top: 8px;
}

.breakdown {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--surface-container-high);
  border-radius: 8px;
}

.breakdown-type {
  font-size: 13px;
  color: var(--on-surface);
  text-transform: capitalize;
}

.breakdown-pct {
  font-size: 14px;
  font-weight: 600;
  color: var(--tertiary);
}

.breakdown-count {
  font-size: 11px;
  color: var(--on-surface-variant);
  margin-left: auto;
}

.suggestions {
  padding: 16px;
  background: var(--primary-container);
  border-radius: 10px;
}

.suggestions h4 {
  font-size: 13px;
  color: var(--on-primary);
  margin-bottom: 12px;
}

.suggestions ul {
  margin: 0;
  padding-left: 20px;
}

.suggestions li {
  font-size: 12px;
  color: var(--on-primary);
  margin-bottom: 6px;
}

/* Visualization Section */
.viz-section {
  height: 100%;
}

.viz-controls {
  display: flex;
  gap: 8px;
}

.viz-controls select {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 12px;
}

.viz-container {
  position: relative;
  height: 400px;
  background: var(--surface-container-high);
  border-radius: 12px;
  overflow: hidden;
}

.viz-stats {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--on-surface-variant);
  z-index: 10;
}

.viz-canvas {
  position: relative;
  width: 100%;
  height: 100%;
}

.viz-point {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: transform 0.1s, opacity 0.15s;
}

.viz-point.viz-hover {
  transform: translate(-50%, -50%) scale(1.8);
  z-index: 5;
}

.viz-point.viz-selected {
  transform: translate(-50%, -50%) scale(1.8);
  box-shadow: 0 0 0 2px var(--surface-container-high), 0 0 0 4px #fff;
  z-index: 6;
}

.viz-point.viz-dim {
  opacity: 0.1;
}

.viz-tooltip {
  position: absolute;
  z-index: 20;
  max-width: 300px;
  max-height: 140px;
  overflow: hidden;
  padding: 8px 10px;
  background: var(--surface-container-highest);
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  pointer-events: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
}

.tooltip-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--primary-container);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tooltip-text {
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.viz-quality {
  color: var(--tertiary);
}

.legend-item {
  cursor: pointer;
}

.legend-item.active {
  color: var(--on-surface);
}

.legend-item.active .legend-color {
  box-shadow: 0 0 0 2px var(--surface-container-high), 0 0 0 3px var(--primary-container);
}

.viz-detail {
  margin-top: 12px;
  padding: 12px 14px;
  background: var(--surface-container);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  margin-bottom: 6px;
}

.detail-meta {
  color: var(--on-surface-variant);
  flex: 1;
}

.detail-close {
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
}

.detail-text {
  font-size: 12px;
  color: var(--on-surface);
  line-height: 1.5;
  max-height: 160px;
  overflow-y: auto;
}

.viz-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--on-surface-variant);
}

.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

/* Quality Section */
.overall-score {
  text-align: center;
  padding: 30px;
  background: var(--tertiary-container);
  border-radius: 12px;
  margin-bottom: 20px;
}

.score-value {
  font-size: 48px;
  font-weight: 700;
  color: var(--tertiary);
}

.score-label {
  display: block;
  font-size: 13px;
  color: var(--on-surface-variant);
  margin-top: 8px;
}

.quality-list {
  margin-bottom: 20px;
}

.quality-chunks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quality-summary {
  font-size: 12px;
  color: var(--on-surface-variant);
  text-align: center;
  margin-top: -10px;
  margin-bottom: 16px;
}

.quality-error {
  padding: 10px 14px;
  margin-bottom: 12px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 8px;
  color: var(--text-main);
  font-size: 12px;
}

.quality-empty {
  padding: 20px 16px;
  border: 1px dashed var(--outline-variant);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.quality-list h4 {
  font-size: 13px;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.quality-item {
  padding: 12px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  margin-bottom: 8px;
}

.quality-item.high {
  border-left: 3px solid var(--tertiary);
}

.quality-item.low {
  border-left: 3px solid var(--tertiary);
}

.quality-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.quality-score {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

.quality-source {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.quality-text {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-bottom: 6px;
}

.quality-meta {
  font-size: 10px;
  color: var(--on-surface-variant);
  opacity: 0.7;
}

.quality-issues {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.issue-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--tertiary-container);
  border-radius: 4px;
  color: var(--tertiary);
}

/* Trace Section */
.trace-input {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.trace-results {
  max-width: 700px;
}

.trace-summary {
  display: flex;
  justify-content: space-between;
  padding: 16px;
  background: var(--primary-container);
  border-radius: 10px;
  margin-bottom: 16px;
}

.total-time {
  font-size: 24px;
  font-weight: 700;
  color: var(--on-primary);
}

.bottleneck {
  font-size: 13px;
  color: var(--on-primary);
}

.trace-stage {
  padding: 12px;
  background: var(--surface-container-high);
  border-radius: 8px;
  margin-bottom: 8px;
}

.stage-header {
  display: flex;
  justify-content: space-between;
}

.stage-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
}

.stage-time {
  font-size: 12px;
  color: var(--primary-container);
}

.stage-results {
  margin-top: 8px;
  font-size: 11px;
  color: var(--on-surface-variant);
}

/* A/B Test Section */
.abtest-section {
  max-width: 800px;
}

.create-test {
  padding: 20px;
  background: var(--surface-container-high);
  border-radius: 12px;
  margin-bottom: 24px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 11px;
  color: var(--on-surface-variant);
  margin-bottom: 6px;
  text-transform: uppercase;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container);
  color: var(--on-surface);
  font-size: 13px;
}

.variant-input {
  margin-bottom: 6px;
}

.abtest-hint {
  font-size: 12px;
  color: var(--on-surface-variant);
  background: var(--surface-container);
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
  line-height: 1.5;
}

.split-inputs {
  display: flex;
  gap: 8px;
}

.split-inputs input {
  width: 70px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 13px;
}

.variant-editor {
  border: 1px solid var(--outline-variant);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--surface-container);
}

.variant-name-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.variant-name-row input {
  flex: 1;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 13px;
}

.variant-config {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.variant-config label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.variant-config input[type="number"] {
  width: 64px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 12px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  text-transform: none !important;
}

.test-variants {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  margin: 0 12px;
  min-width: 0;
}

.test-variant {
  display: flex;
  gap: 8px;
  font-size: 11px;
  align-items: baseline;
}

.test-variant-name {
  font-weight: 600;
  color: var(--on-surface);
  flex-shrink: 0;
}

.test-variant-config {
  color: var(--on-surface-variant);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tests-list {
  margin-bottom: 24px;
}

.tests-list h3 {
  font-size: 14px;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.test-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--surface-container-high);
  border-radius: 8px;
  margin-bottom: 8px;
}

.test-name {
  font-size: 13px;
  color: var(--on-surface);
}

.test-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.test-status.draft {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
}

.test-status.running {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.test-status.completed {
  background: rgba(99, 102, 241, 0.2);
  color: #6366f1;
}

.test-actions {
  display: flex;
  gap: 6px;
}

.results-modal {
  padding: 16px;
  background: var(--surface-container-high);
  border-radius: 10px;
}

.results-modal h4 {
  font-size: 13px;
  color: var(--on-surface);
  margin-bottom: 12px;
}

.result-row {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--outline-variant);
  font-size: 12px;
  color: var(--on-surface-variant);
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  color: var(--on-primary);
}

/* Phase 3: Alerts */
.alerts-section { max-width: 800px; }
.alert-item { padding: 16px; background: var(--surface-container-high); border-radius: 10px; margin-bottom: 12px; border-left: 3px solid; }
.alert-item.warning { border-color: var(--tertiary); }
.alert-item.critical { border-color: var(--tertiary); }
.alert-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.alert-type { font-size: 13px; font-weight: 600; color: var(--on-surface); text-transform: capitalize; }
.alert-time { font-size: 11px; color: var(--on-surface-variant); }
.alert-message { font-size: 14px; color: var(--on-surface); margin-bottom: 8px; }
.alert-details { font-size: 12px; color: var(--on-surface-variant); margin-bottom: 12px; }
.alert-actions { display: flex; gap: 8px; }

/* Phase 3: Capacity */
.capacity-section { max-width: 800px; }
.forecast-stats { display: flex; gap: 24px; margin-bottom: 24px; }
.forecast-card { padding: 20px; background: var(--surface-container-high); border-radius: 12px; text-align: center; flex: 1; }
.forecast-label { font-size: 12px; color: var(--on-surface-variant); margin-bottom: 8px; }
.forecast-value { font-size: 32px; font-weight: 700; color: var(--on-surface); }
.forecast-range { font-size: 11px; color: var(--on-surface-variant); }
.recommendations { padding: 16px; background: var(--primary-container); border-radius: 10px; }
.rec-item { display: flex; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--outline-variant); font-size: 13px; }
.rec-date { color: var(--primary-container); }
.rec-action { color: var(--on-primary); font-weight: 600; }
.rec-details { color: var(--on-primary); }

/* Phase 3: Self-Heal */
.selfheal-section { max-width: 800px; }
.event-item { padding: 12px; background: var(--surface-container-high); border-radius: 8px; margin-bottom: 8px; display: grid; grid-template-columns: 80px 1fr 1fr 1fr; gap: 12px; font-size: 12px; align-items: center; }
.event-time { color: var(--on-surface-variant); }
.event-trigger { color: var(--tertiary); }
.event-action { color: var(--tertiary); }
.event-result { color: var(--on-surface-variant); }

/* Phase 3: Cost */
.cost-section { max-width: 800px; }
.cost-summary { text-align: center; padding: 30px; background: var(--tertiary-container); border-radius: 12px; margin-bottom: 20px; }
.cost-value { font-size: 48px; font-weight: 700; color: var(--tertiary); }
.cost-label { display: block; font-size: 13px; color: var(--on-surface-variant); margin-top: 8px; }
.cost-breakdown { margin-bottom: 20px; }
.cost-item { display: grid; grid-template-columns: 150px 1fr 80px 60px; gap: 12px; align-items: center; margin-bottom: 12px; }
.cost-name { font-size: 13px; color: var(--on-surface); }
.cost-bar { height: 8px; background: var(--outline-variant); border-radius: 4px; overflow: hidden; }
.cost-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary-container), var(--primary)); }
.cost-amount { font-size: 13px; color: var(--on-surface); text-align: right; }
.cost-pct { font-size: 12px; color: var(--on-surface-variant); }
.cost-recs { padding: 16px; background: var(--tertiary-container); border-radius: 10px; }
.cost-recs h4 { font-size: 13px; color: var(--on-tertiary); margin-bottom: 12px; }
.rec-text { font-size: 12px; color: var(--on-tertiary); padding: 6px 0; }

/* Phase 3: Users */
.users-section { max-width: 800px; }
.user-stats { display: flex; gap: 24px; margin-bottom: 24px; }
.user-stat { padding: 20px; background: var(--surface-container-high); border-radius: 12px; text-align: center; flex: 1; }
.user-value { display: block; font-size: 32px; font-weight: 700; color: var(--on-surface); }
.user-label { font-size: 12px; color: var(--on-surface-variant); }
.user-segments h4 { font-size: 13px; color: var(--on-surface); margin-bottom: 12px; }
.segment-item { display: flex; justify-content: space-between; padding: 10px; background: var(--surface-container-high); border-radius: 8px; margin-bottom: 6px; }
.seg-name { font-size: 13px; color: var(--on-surface); }
.seg-pct { font-size: 13px; color: var(--primary-container); font-weight: 600; }

/* Phase 3: Reports */
.reports-section { max-width: 800px; }
.report-form { display: flex; gap: 16px; align-items: flex-end; margin-bottom: 24px; padding: 16px; background: var(--surface-container-high); border-radius: 10px; }
.report-form .form-group { margin: 0; }
.report-form select { padding: 8px 14px; border-radius: 8px; border: 1px solid var(--outline-variant); background: var(--surface-container); color: var(--on-surface); font-size: 13px; }
.reports-list h4 { font-size: 13px; color: var(--on-surface); margin-bottom: 12px; }
.report-item { display: flex; justify-content: space-between; padding: 10px; background: var(--surface-container-high); border-radius: 8px; margin-bottom: 6px; font-size: 12px; }
.report-type { color: var(--primary-container); text-transform: capitalize; }
.report-date { color: var(--on-surface-variant); }

/* Phase 3: Health */
.health-section { max-width: 800px; }
.health-score { text-align: center; padding: 30px; background: var(--tertiary-container); border-radius: 12px; margin-bottom: 24px; }
.score-big { font-size: 64px; font-weight: 700; color: var(--tertiary); }
.score-label { font-size: 18px; color: var(--on-surface-variant); }
.dimension-scores { margin-bottom: 24px; }
.dim-item { display: grid; grid-template-columns: 100px 1fr 50px; gap: 12px; align-items: center; margin-bottom: 12px; }
.dim-name { font-size: 13px; color: var(--on-surface); }
.dim-bar { height: 8px; background: var(--outline-variant); border-radius: 4px; overflow: hidden; }
.dim-bar-fill { height: 100%; background: var(--tertiary); }
.dim-score { font-size: 13px; color: var(--on-surface); text-align: right; }
.health-issues h4 { font-size: 13px; color: var(--on-surface); margin-bottom: 12px; }
.issue-item { display: flex; align-items: center; gap: 12px; padding: 10px; background: var(--surface-container-high); border-radius: 8px; margin-bottom: 6px; }
.issue-priority { font-size: 10px; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; }
.issue-priority.high { background: var(--tertiary-container); color: var(--tertiary); }
.issue-priority.medium { background: var(--tertiary-container); color: var(--tertiary); }
.issue-priority.low { background: var(--surface-container-high); color: var(--on-surface-variant); }
.issue-message { font-size: 12px; color: var(--on-surface-variant); }
</style>
