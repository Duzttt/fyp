<script setup>
import { ref, onMounted, computed } from 'vue'
import { Line, Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
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
} from 'chart.js'
import {
  getAdminStats,
  getAdminQueryStats,
  debugRetrieval,
  getAdminDocuments,
  getAdminDocumentChunks,
  deleteAdminDocument,
  reindexAdminDocument,
  getAdminIndexingStatus
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

const tabs = [
  { id: 'overview', label: 'System Overview', icon: '📊' },
  { id: 'retrieval', label: 'Retrieval Debug', icon: '🔍' },
  { id: 'documents', label: 'Documents', icon: '📄' },
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
    alert('Debug retrieval failed: ' + err.message)
  } finally {
    debugLoading.value = false
  }
}

const handleDeleteDocument = async (docId) => {
  if (!confirm(`Delete document "${docId}"? This will rebuild the index.`)) return
  
  try {
    await deleteAdminDocument(docId)
    alert('Document deleted successfully')
    await loadDocuments()
  } catch (err) {
    alert('Failed to delete document: ' + err.message)
  }
}

const handleReindexDocument = async (docId) => {
  try {
    await reindexAdminDocument(docId)
    alert('Document reindexed successfully')
  } catch (err) {
    alert('Failed to reindex document: ' + err.message)
  }
}

const handleViewChunks = (doc) => {
  selectedDoc.value = doc
  loadChunks(doc.id, 1)
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

onMounted(async () => {
  loading.value = true
  await Promise.all([loadStats(), loadQueryStats(), loadDocuments(), loadIndexingStatus()])
  loading.value = false
  
  // Poll indexing status
  setInterval(loadIndexingStatus, 3000)
})
</script>

<template>
  <div class="admin-panel">
    <div class="admin-header">
      <div class="admin-title">
        <span class="title-icon">🛠️</span>
        <span>Admin Dashboard</span>
      </div>
      <div class="admin-actions">
        <span class="status-badge" :class="indexingStatus.status">
          {{ indexingStatus.status === 'running' ? '⏳ Indexing...' : '✓ Ready' }}
        </span>
        <button class="close-btn" @click="emit('close')">✕</button>
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
                @input="loadDocuments"
              />
              <button class="refresh-btn" @click="loadDocuments">↻</button>
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
                <button class="action-btn view" @click="handleViewChunks(doc)">View Chunks</button>
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
    </div>
  </div>
</template>

<style scoped>
.admin-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(1100px, 95vw);
  height: min(850px, 90vh);
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(99, 102, 241, 0.1);
}

.admin-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: white;
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
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.tab-nav {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main);
}

.tab-btn.active {
  background: rgba(99, 102, 241, 0.2);
  color: white;
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
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: #6366f1;
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
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
  color: white;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.stat-sub {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Health Section */
.health-section, .query-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}

.health-label {
  font-size: 11px;
  color: var(--text-muted);
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
  color: white;
}

.query-label {
  font-size: 11px;
  color: var(--text-muted);
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
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}

.type-name {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: capitalize;
}

.type-count {
  font-size: 12px;
  font-weight: 600;
  color: white;
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
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: white;
  font-size: 14px;
  outline: none;
}

.query-input:focus {
  border-color: #6366f1;
}

.search-btn {
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  color: white;
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
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-group label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.param-group input,
.param-group select {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: white;
  font-size: 13px;
  outline: none;
}

.debug-results {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.result-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
}

.result-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.result-section .time {
  font-size: 11px;
  color: var(--text-muted);
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
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.result-rank {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.2);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  flex-shrink: 0;
}

.result-content {
  flex: 1;
  min-width: 0;
}

.result-score {
  font-size: 11px;
  color: #22c55e;
  font-weight: 600;
}

.result-text {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-source {
  font-size: 10px;
  color: var(--text-muted);
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
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: white;
  font-size: 13px;
  outline: none;
  width: 200px;
}

.refresh-btn {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-muted);
  cursor: pointer;
}

.loading-small {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}

.doc-info {
  flex: 1;
}

.doc-name {
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.doc-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.doc-date {
  font-size: 11px;
  color: var(--text-muted);
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
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.action-btn.delete:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
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
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-muted);
  cursor: pointer;
}

.chunks-count {
  font-size: 12px;
  color: var(--text-muted);
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
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
  color: #6366f1;
}

.chunk-page {
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
}

.chunk-text {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.chunk-embedding {
  font-size: 10px;
  color: var(--text-muted);
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
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-muted);
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: var(--text-muted);
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
</style>
