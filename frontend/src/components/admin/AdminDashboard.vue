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
  acknowledgeAlert,
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
  getAdminFailureAnalysis,
  getAdminIndexingStatus,
  getAdminQueryClusters,
  getAdminQueryStats,
  getAdminStats,
  getCapacityForecast,
  getCostAnalysis,
  getCurrentAlerts,
  getHealthScore,
  getReportsHistory,
  getSelfHealingEvents,
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
const docAnalytics = ref(null)
const queryClusters = ref({ clusters: [], total_queries: 0 })
const failureAnalysis = ref({ failure_rate: 0, breakdown: [], suggestions: [] })
const embeddingViz = ref({ points: [], documents: [] })
const chunkQuality = ref({ top_chunks: [], low_quality_chunks: [], overall_score: 0 })
const traceResults = ref(null)
const abTests = ref([])

// Phase 3: Smart Operations data
const alerts = ref({ active_alerts: [], history: [] })
const capacityForecast = ref({ historical: {}, forecast: {}, recommendations: [] })
const selfHealingEvents = ref({ events: [], policies: [] })
const costAnalysis = ref({ total: 0, breakdown: [], recommendations: [] })
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
const traceQuery = ref('')
const traceLoading = ref(false)

// New test form
const newTestForm = ref({
  name: '',
  description: '',
  variants: [{ name: 'control', config: {} }, { name: 'variant_a', config: {} }],
})

const tabs = [
  { id: 'overview', label: 'System Overview', icon: '📊' },
  { id: 'retrieval', label: 'Retrieval Debug', icon: '🔍' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'analytics', label: 'Analytics', icon: '📈' },
  { id: 'clusters', label: 'Query Clusters', icon: '🔮' },
  { id: 'failures', label: 'Failures', icon: '⚠️' },
  { id: 'viz', label: 'Vector Viz', icon: '🌌' },
  { id: 'quality', label: 'Chunk Quality', icon: '⭐' },
  { id: 'trace', label: 'Trace', icon: '🔎' },
  { id: 'abtest', label: 'A/B Test', icon: '🔬' },
  { id: 'alerts', label: 'Alerts', icon: '🔔' },
  { id: 'capacity', label: 'Capacity', icon: '📈' },
  { id: 'selfheal', label: 'Self-Heal', icon: '🔧' },
  { id: 'cost', label: 'Cost', icon: '💰' },
  { id: 'users', label: 'Users', icon: '👥' },
  { id: 'reports', label: 'Reports', icon: '📑' },
  { id: 'health', label: 'Health', icon: '❤️' },
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

const loadChunks = async (docId, page = 1) => {
  chunksLoading.value = true
  currentPage.value = page
  try {
    const data = await getAdminDocumentChunks(docId, page, pageSize.value)
    documentChunks.value = data.chunks
    totalChunks.value = data.total
  } catch (err) {
    console.error('Failed to load chunks:', err)
  } finally {
    chunksLoading.value = false
  }
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
  
  try {
    await deleteAdminDocument(docId)
    notify('Document deleted successfully', 'success')
    await loadDocuments()
  } catch (err) {
    notify('Failed to delete document: ' + err.message, 'error')
  }
}

const handleReindexDocument = async (docId) => {
  try {
    await reindexAdminDocument(docId)
    notify('Document reindexed successfully', 'success')
  } catch (err) {
    notify('Failed to reindex document: ' + err.message, 'error')
  }
}

const handleViewChunks = (doc) => {
  selectedDoc.value = doc
  loadChunks(doc.id, 1)
}

const handleViewDocAnalytics = async (doc) => {
  selectedDocForAnalytics.value = doc
  await loadDocumentAnalytics(doc.id)
  activeTab.value = 'analytics'
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
  analyticsLoading.value = true
  try {
    const data = await getAdminDocumentAnalytics(docId)
    docAnalytics.value = data
  } catch (err) {
    console.error('Failed to load document analytics:', err)
  } finally {
    analyticsLoading.value = false
  }
}

const loadQueryClusters = async () => {
  analyticsLoading.value = true
  try {
    const data = await getAdminQueryClusters(30, 1000)
    queryClusters.value = data
  } catch (err) {
    console.error('Failed to load query clusters:', err)
  } finally {
    analyticsLoading.value = false
  }
}

const loadFailureAnalysis = async () => {
  analyticsLoading.value = true
  try {
    const data = await getAdminFailureAnalysis(24)
    failureAnalysis.value = data
  } catch (err) {
    console.error('Failed to load failure analysis:', err)
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
    newTestForm.value = { name: '', description: '', variants: [{ name: 'control', config: {} }, { name: 'variant_a', config: {} }] }
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

// Phase 3: Load functions
const loadAlerts = async () => {
  try {
    const data = await getCurrentAlerts()
    alerts.value = data
  } catch (err) {
    console.error('Failed to load alerts:', err)
  }
}

const loadCapacityForecast = async () => {
  try {
    const data = await getCapacityForecast(3)
    capacityForecast.value = data
  } catch (err) {
    console.error('Failed to load forecast:', err)
  }
}

const loadSelfHealing = async () => {
  try {
    const data = await getSelfHealingEvents()
    selfHealingEvents.value = data
  } catch (err) {
    console.error('Failed to load self-healing:', err)
  }
}

const loadCostAnalysis = async () => {
  try {
    const data = await getCostAnalysis()
    costAnalysis.value = data
  } catch (err) {
    console.error('Failed to load cost analysis:', err)
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
  await Promise.all([loadStats(), loadQueryStats(), loadDocuments(), loadIndexingStatus(), loadABTests(), loadAlerts(), loadCapacityForecast(), loadSelfHealing(), loadCostAnalysis(), loadUserBehavior(), loadReports(), loadHealthScore()])
  loading.value = false
  
  // Poll indexing status
  indexingInterval = setInterval(loadIndexingStatus, 3000)
  // Poll alerts
  alertsInterval = setInterval(loadAlerts, 60000)
})

let indexingInterval = null
let alertsInterval = null

onBeforeUnmount(() => {
  if (indexingInterval) clearInterval(indexingInterval)
  if (alertsInterval) clearInterval(alertsInterval)
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
    <div class="tab-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

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
            <div class="stat-icon docs">📄</div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.documents.total }}</div>
              <div class="stat-label">Documents</div>
              <div class="stat-sub">{{ stats.documents.chunks }} chunks · {{ stats.documents.pages }} pages</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon vectors">📏</div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.vectors.count.toLocaleString() }}</div>
              <div class="stat-label">Vectors</div>
              <div class="stat-sub">{{ stats.vectors.index_type }} · {{ stats.vectors.dimension }}D</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon queries">⚡</div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.queries.today }}</div>
              <div class="stat-label">Today's Queries</div>
              <div class="stat-sub">{{ stats.queries.week }} this week</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon latency">⏱️</div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.queries.avg_latency_ms }}ms</div>
              <div class="stat-label">Avg Latency</div>
              <div class="stat-sub">P95: {{ stats.queries.p95_latency_ms }}ms</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon cache">💾</div>
            <div class="stat-body">
              <div class="stat-value">{{ stats.queries.cache_hit_rate }}%</div>
              <div class="stat-label">Cache Hit Rate</div>
              <div class="stat-sub">7-day average</div>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon storage">💽</div>
            <div class="stat-body">
              <div class="stat-value">{{ formatSize(stats.storage.faiss_size_kb) }}</div>
              <div class="stat-label">Index Size</div>
              <div class="stat-sub">Docs: {{ formatSize(stats.storage.docs_size_kb) }}</div>
            </div>
          </div>
        </div>

        <!-- Health Status -->
        <div class="health-section">
          <h3 class="section-title">System Health</h3>
          <div class="health-grid">
            <div class="health-item">
              <span class="health-label">FAISS Index</span>
              <span class="health-status" :style="{ color: getHealthColor(stats.health.faiss_index) }">
                {{ stats.health.faiss_index }}
              </span>
            </div>
            <div class="health-item">
              <span class="health-label">LLM Service</span>
              <span class="health-status" :style="{ color: getHealthColor(stats.health.llm_service) }">
                {{ stats.health.llm_service }}
              </span>
            </div>
            <div class="health-item">
              <span class="health-label">Disk Space</span>
              <span class="health-status" :style="{ color: getHealthColor(stats.health.disk_space) }">
                {{ stats.health.disk_space }}
              </span>
            </div>
            <div class="health-item">
              <span class="health-label">Memory</span>
              <span class="health-status" :style="{ color: getHealthColor(stats.health.memory) }">
                {{ stats.health.memory }}
              </span>
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
            <div v-for="item in queryStats.type_distribution" :key="item.query_type" class="type-item">
              <span class="type-name">{{ item.query_type }}</span>
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
              <div class="result-list">
                <div v-for="(r, i) in debugResults.bm25?.results" :key="'bm25-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="result-section">
              <h4>Dense (Vector) <span class="time">{{ debugResults.dense?.time_ms }}ms</span></h4>
              <div class="result-list">
                <div v-for="(r, i) in debugResults.dense?.results" :key="'dense-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="result-section">
              <h4>Hybrid <span class="time">{{ debugResults.hybrid?.time_ms }}ms ({{ debugResults.hybrid?.fusion_method }})</span></h4>
              <div class="result-list">
                <div v-for="(r, i) in debugResults.hybrid?.results" :key="'hybrid-'+i" class="result-item">
                  <span class="result-rank">{{ i + 1 }}</span>
                  <div class="result-content">
                    <div class="result-score">Score: {{ r.score }}</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">{{ r.source }}</div>
                  </div>
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
                <button class="action-btn reindex" @click="handleReindexDocument(doc.id)">Reindex</button>
                <button class="action-btn delete" @click="handleDeleteDocument(doc.id)">Delete</button>
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
              <div v-if="chunk.embedding_preview" class="chunk-embedding">
                Embedding: [{{ chunk.embedding_preview.join(', ') }}...]
              </div>
            </div>
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
              <button class="back-btn" @click="selectedDocForAnalytics = null">← Back</button>
              <h3>{{ selectedDocForAnalytics.name }}</h3>
            </div>
            
            <div v-if="docAnalytics" class="analytics-stats">
              <div class="stat-card">
                <div class="stat-value">{{ docAnalytics.retrieval_stats.appearance_count }}</div>
                <div class="stat-label">Appearance Count</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{{ docAnalytics.retrieval_stats.avg_score }}</div>
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
            
            <div v-if="docAnalytics" class="top-queries">
              <h4>Top Queries</h4>
              <div v-for="q in docAnalytics.top_queries" :key="q.query" class="query-item">
                <span class="query-text">{{ q.query }}</span>
                <span class="query-count">{{ q.count }} times</span>
              </div>
            </div>
            <div v-else class="empty-state">Failed to load document analytics</div>
          </div>
          
          <div v-else class="select-doc">
            <h3>Select a Document</h3>
            <p>Choose a document from the Documents tab to view analytics</p>
            <button class="action-btn" @click="activeTab = 'documents'">Go to Documents</button>
          </div>
        </div>
      </div>

      <!-- Query Clusters Tab -->
      <div v-else-if="activeTab === 'clusters'" class="tab-content">
        <div class="clusters-section">
          <div class="section-header">
            <h3>Query Semantic Clusters</h3>
            <button class="refresh-btn" aria-label="Refresh query clusters" title="Refresh query clusters" @click="loadQueryClusters">↻</button>
          </div>
          
          <div v-if="queryClusters.clusters?.length" class="clusters-list">
            <div v-for="cluster in queryClusters.clusters" :key="cluster.name" class="cluster-item">
              <div class="cluster-header">
                <span class="cluster-color" :style="{ background: cluster.color }"></span>
                <span class="cluster-name">{{ cluster.name.replace('_', ' ') }}</span>
                <span class="cluster-pct">{{ cluster.percentage }}%</span>
              </div>
              <div class="cluster-patterns">
                <span v-for="p in cluster.patterns" :key="p" class="pattern-tag">{{ p }}</span>
              </div>
              <div class="cluster-sample">
                <strong>Representative:</strong> {{ cluster.representative }}
              </div>
            </div>
          </div>
          <div v-else class="empty-state">No cluster data available</div>
        </div>
      </div>

      <!-- Failures Tab -->
      <div v-else-if="activeTab === 'failures'" class="tab-content">
        <div class="failures-section">
          <div class="section-header">
            <h3>Retrieval Failure Analysis</h3>
            <button class="refresh-btn" aria-label="Refresh failure analysis" title="Refresh failure analysis" @click="loadFailureAnalysis">↻</button>
          </div>
          
          <div class="failure-rate">
            <span class="rate-value">{{ (failureAnalysis.failure_rate * 100).toFixed(1) }}%</span>
            <span class="rate-label">Failure Rate (24h)</span>
          </div>
          
          <div v-if="failureAnalysis.breakdown?.length" class="breakdown">
            <div v-for="item in failureAnalysis.breakdown" :key="item.type" class="breakdown-item">
              <span class="breakdown-type">{{ item.type.replace('_', ' ') }}</span>
              <span class="breakdown-pct">{{ item.percentage }}%</span>
              <span class="breakdown-count">({{ item.count }} queries)</span>
            </div>
          </div>
          
          <div v-if="failureAnalysis.suggestions?.length" class="suggestions">
            <h4>Suggestions</h4>
            <ul>
              <li v-for="s in failureAnalysis.suggestions" :key="s">{{ s }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Vector Viz Tab -->
      <div v-else-if="activeTab === 'viz'" class="tab-content">
        <div class="viz-section">
          <div class="section-header">
            <h3>Embedding Visualization</h3>
            <div class="viz-controls">
              <select v-model="vizMethod" @change="loadEmbeddingViz">
                <option value="pca">PCA</option>
                <option value="tsne">t-SNE</option>
              </select>
              <button class="refresh-btn" aria-label="Refresh embedding visualization" title="Refresh embedding visualization" @click="loadEmbeddingViz">↻</button>
            </div>
          </div>
          
          <div v-if="embeddingViz.points?.length" class="viz-container">
            <div class="viz-stats">
              <span>{{ embeddingViz.points.length }} points</span>
              <span>{{ embeddingViz.documents?.length }} documents</span>
            </div>
            <div class="viz-canvas">
              <div v-for="(point, i) in embeddingViz.points" :key="i" 
                class="viz-point"
                :style="{ 
                  left: ((point.x - embeddingBounds.minX) / embeddingBounds.xRange * 100) + '%',
                  top: ((point.y - embeddingBounds.minY) / embeddingBounds.yRange * 100) + '%',
                  background: point.document_color
                }"
                :title="point.text_preview"
              ></div>
            </div>
            <div class="viz-legend">
              <div v-for="doc in embeddingViz.documents" :key="doc" class="legend-item">
                <span class="legend-color" :style="{ background: embeddingViz.points.find(p => p.document === doc)?.document_color }"></span>
                <span>{{ doc }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">No visualization data available</div>
        </div>
      </div>

      <!-- Chunk Quality Tab -->
      <div v-else-if="activeTab === 'quality'" class="tab-content">
        <div class="quality-section">
          <div class="section-header">
            <h3>Chunk Quality Assessment</h3>
            <button class="refresh-btn" aria-label="Refresh chunk quality metrics" title="Refresh chunk quality metrics" @click="loadChunkQuality">↻</button>
          </div>
          
          <div class="overall-score">
            <span class="score-value">{{ chunkQuality.overall_score || 0 }}</span>
            <span class="score-label">/ 100 Overall Score</span>
          </div>
          
          <div class="quality-list">
            <h4>Top Quality Chunks</h4>
            <div v-for="chunk in chunkQuality.top_chunks" :key="chunk.index" class="quality-item high">
              <div class="quality-header">
                <span class="quality-score">{{ chunk.quality_score }}</span>
                <span class="quality-source">{{ chunk.source }}</span>
              </div>
              <div class="quality-text">{{ chunk.text_preview }}</div>
              <div class="quality-meta">Hits: {{ chunk.retrieval_hits }} · Issues: {{ chunk.issues?.length || 0 }}</div>
            </div>
          </div>
          
          <div class="quality-list">
            <h4>Low Quality Chunks (Needs Fix)</h4>
            <div v-for="chunk in chunkQuality.low_quality_chunks" :key="chunk.index" class="quality-item low">
              <div class="quality-header">
                <span class="quality-score">{{ chunk.quality_score }}</span>
                <span class="quality-source">{{ chunk.source }}</span>
              </div>
              <div class="quality-text">{{ chunk.text_preview }}</div>
              <div v-if="chunk.issues?.length" class="quality-issues">
                <span v-for="issue in chunk.issues" :key="issue" class="issue-tag">{{ issue }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Trace Tab -->
      <div v-else-if="activeTab === 'trace'" class="tab-content">
        <div class="trace-section">
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

      <!-- A/B Test Tab -->
      <div v-else-if="activeTab === 'abtest'" class="tab-content">
        <div class="abtest-section">
          <div class="create-test">
            <h3>Create New A/B Test</h3>
            <div class="form-group">
              <label>Test Name</label>
              <input v-model="newTestForm.name" type="text" placeholder="Test name..." />
            </div>
            <div class="form-group">
              <label>Description</label>
              <textarea v-model="newTestForm.description" placeholder="Description..."></textarea>
            </div>
            <div class="form-group">
              <label>Variants</label>
              <div v-for="(v, i) in newTestForm.variants" :key="i" class="variant-input">
                <input v-model="v.name" type="text" :placeholder="'Variant ' + (i + 1)" />
              </div>
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
              <div class="test-actions">
                <button v-if="test.status === 'draft'" class="action-btn" @click="handleStartTest(test.id)">Start</button>
                <button v-if="test.status === 'running'" class="action-btn" @click="handleStopTest(test.id)">Stop</button>
                <button class="action-btn" @click="handleViewResults(test.id)">Results</button>
              </div>
            </div>
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

      <!-- Alerts Tab -->
      <div v-else-if="activeTab === 'alerts'" class="tab-content">
        <div class="alerts-section">
          <div class="section-header">
            <h3>🔔 Smart Alerts</h3>
            <button class="refresh-btn" aria-label="Refresh alerts" title="Refresh alerts" @click="loadAlerts">↻</button>
          </div>
          
          <div class="active-alerts">
            <h4>Active Alerts ({{ alerts.active_alerts?.length || 0 }})</h4>
            <div v-for="alert in alerts.active_alerts" :key="alert.id" class="alert-item" :class="alert.severity">
              <div class="alert-header">
                <span class="alert-type">{{ alert.type }}</span>
                <span class="alert-time">{{ alert.start_time }}</span>
              </div>
              <div class="alert-message">{{ alert.message }}</div>
              <div class="alert-details">
                <span>Current: {{ alert.current_value }}</span>
                <span>Baseline: {{ alert.baseline?.avg }}</span>
              </div>
              <div class="alert-actions">
                <button class="action-btn" @click="acknowledgeAlert(alert.id, 'acknowledge')">Acknowledge</button>
                <button class="action-btn" @click="acknowledgeAlert(alert.id, 'ignore')">Ignore</button>
              </div>
            </div>
            <div v-if="!alerts.active_alerts?.length" class="empty-state">No active alerts</div>
          </div>
        </div>
      </div>

      <!-- Capacity Tab -->
      <div v-else-if="activeTab === 'capacity'" class="tab-content">
        <div class="capacity-section">
          <div class="section-header">
            <h3>📈 Capacity Forecast</h3>
            <button class="refresh-btn" aria-label="Refresh capacity forecast" title="Refresh capacity forecast" @click="loadCapacityForecast">↻</button>
          </div>
          
          <div class="forecast-stats">
            <div class="forecast-card">
              <div class="forecast-label">Documents</div>
              <div class="forecast-value">{{ capacityForecast.forecast?.documents?.value || 0 }}</div>
              <div class="forecast-range">({{ capacityForecast.forecast?.documents?.lower }} - {{ capacityForecast.forecast?.documents?.upper }})</div>
            </div>
            <div class="forecast-card">
              <div class="forecast-label">Queries/Day</div>
              <div class="forecast-value">{{ capacityForecast.forecast?.queries_per_day?.value || 0 }}</div>
              <div class="forecast-range">({{ capacityForecast.forecast?.queries_per_day?.lower }} - {{ capacityForecast.forecast?.queries_per_day?.upper }})</div>
            </div>
          </div>
          
          <div v-if="capacityForecast.recommendations?.length" class="recommendations">
            <h4>Recommendations</h4>
            <div v-for="rec in capacityForecast.recommendations" :key="rec.date" class="rec-item">
              <span class="rec-date">{{ rec.date }}</span>
              <span class="rec-action">{{ rec.action }}</span>
              <span class="rec-details">{{ rec.details }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Self-Heal Tab -->
      <div v-else-if="activeTab === 'selfheal'" class="tab-content">
        <div class="selfheal-section">
          <div class="section-header">
            <h3>🔧 Self-Healing Events</h3>
            <button class="refresh-btn" aria-label="Refresh self-healing events" title="Refresh self-healing events" @click="loadSelfHealing">↻</button>
          </div>
          
          <div class="events-list">
            <div v-for="event in selfHealingEvents.events" :key="event.id" class="event-item">
              <div class="event-time">{{ event.timestamp }}</div>
              <div class="event-trigger">{{ event.trigger }}</div>
              <div class="event-action">{{ event.action_taken }}</div>
              <div class="event-result">{{ event.result }}</div>
            </div>
            <div v-if="!selfHealingEvents.events?.length" class="empty-state">No self-healing events</div>
          </div>
        </div>
      </div>

      <!-- Cost Tab -->
      <div v-else-if="activeTab === 'cost'" class="tab-content">
        <div class="cost-section">
          <div class="section-header">
            <h3>💰 Cost Analysis</h3>
            <button class="refresh-btn" aria-label="Refresh cost analysis" title="Refresh cost analysis" @click="loadCostAnalysis">↻</button>
          </div>
          
          <div class="cost-summary">
            <div class="cost-total">
              <span class="cost-value">${{ costAnalysis.total || 0 }}</span>
              <span class="cost-label">Total Cost</span>
            </div>
          </div>
          
          <div class="cost-breakdown">
            <div v-for="item in costAnalysis.breakdown" :key="item.category" class="cost-item">
              <span class="cost-name">{{ item.name }}</span>
              <div class="cost-bar">
                <div class="cost-bar-fill" :style="{ width: item.percentage + '%' }"></div>
              </div>
              <span class="cost-amount">${{ item.cost }}</span>
              <span class="cost-pct">{{ item.percentage }}%</span>
            </div>
          </div>
          
          <div v-if="costAnalysis.recommendations?.length" class="cost-recs">
            <h4>Optimization Suggestions</h4>
            <div v-for="rec in costAnalysis.recommendations" :key="rec" class="rec-text">{{ rec }}</div>
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
      <div v-else-if="activeTab === 'health'" class="tab-content">
        <div class="health-section">
          <div class="section-header">
            <h3>❤️ Knowledge Base Health</h3>
            <button class="refresh-btn" aria-label="Refresh health score" title="Refresh health score" @click="loadHealthScore">↻</button>
          </div>
          
          <div class="health-score">
            <span class="score-big">{{ healthScore.overall_score || 0 }}</span>
            <span class="score-label">/ 100</span>
          </div>
          
          <div class="dimension-scores">
            <div v-for="(dim, key) in healthScore.dimensions" :key="key" class="dim-item">
              <span class="dim-name">{{ dim.label }}</span>
              <div class="dim-bar">
                <div class="dim-bar-fill" :style="{ width: dim.score + '%' }"></div>
              </div>
              <span class="dim-score">{{ dim.score }}</span>
            </div>
          </div>
          
          <div v-if="healthScore.issues?.length" class="health-issues">
            <h4>Issues to Address</h4>
            <div v-for="issue in healthScore.issues" :key="issue.message" class="issue-item" :class="issue.priority">
              <span class="issue-priority">{{ issue.priority }}</span>
              <span class="issue-message">{{ issue.message }}</span>
            </div>
          </div>
        </div>
      </div>
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
  gap: 4px;
  padding: 8px 16px;
  background: var(--surface-container-low);
  border-bottom: 1px solid var(--outline-variant);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: var(--surface-container-high);
  color: var(--on-surface);
}

.tab-btn.active {
  background: var(--primary-container);
  color: var(--on-primary);
}

.tab-icon {
  font-size: 14px;
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
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon.docs { background: rgba(34, 197, 94, 0.15); }
.stat-icon.vectors { background: rgba(99, 102, 241, 0.15); }
.stat-icon.queries { background: rgba(251, 191, 36, 0.15); }
.stat-icon.latency { background: rgba(168, 85, 247, 0.15); }
.stat-icon.cache { background: rgba(236, 72, 153, 0.15); }
.stat-icon.storage { background: rgba(6, 182, 212, 0.15); }

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

/* Health Section */
.health-section, .query-section {
  margin-bottom: 24px;
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

.health-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 10px;
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
  gap: 24px;
  margin-bottom: 12px;
}

.query-stat {
  display: flex;
  flex-direction: column;
}

.query-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--on-surface);
}

.query-label {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.type-dist {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--surface-container-high);
  border-radius: 6px;
}

.type-name {
  font-size: 12px;
  color: var(--on-surface-variant);
  text-transform: capitalize;
}

.type-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
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

.chunk-embedding {
  font-size: 10px;
  color: var(--on-surface-variant);
  margin-top: 8px;
  font-family: monospace;
  opacity: 0.6;
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

.cluster-sample {
  font-size: 12px;
  color: var(--on-surface-variant);
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
