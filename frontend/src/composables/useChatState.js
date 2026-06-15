import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useDocumentStore } from '../stores/documentStore'

const MESSAGES_STORAGE_KEY = 'lecture-qa-messages'
const MAX_STORED_MESSAGES = 100

const messages = ref([])
const isLoading = ref(false)
const error = ref('')
const lastRetrievedChunks = ref([])
const isRetrieving = ref(false)

// PDF Viewer state
const showPdfViewer = ref(false)
const currentPdfUrl = ref('')
const currentPdfPage = ref(1)
const currentHighlightText = ref('')

// Bidirectional citations state
const showBidirectionalPanel = ref(false)
const selectedCitation = ref({ source: '', page: null, text: '' })
const bidirectionalIndex = ref({})

let activeController = null

const loadMessages = () => {
  try {
    const stored = localStorage.getItem(MESSAGES_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed)) {
        messages.value = parsed.slice(-MAX_STORED_MESSAGES)
      }
    }
  } catch {
    // ignore corrupted data
  }
}

const saveMessages = () => {
  try {
    const toStore = messages.value.slice(-MAX_STORED_MESSAGES)
    localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(toStore))
  } catch {
    // storage full or unavailable
  }
}

const registerCitations = (messageId, query, answer, chunks) => {
  chunks.forEach(chunk => {
    const key = `${chunk.source}_${chunk.page}_${(chunk.text || '').substring(0, 50)}`
    if (!bidirectionalIndex.value[key]) {
      bidirectionalIndex.value[key] = []
    }
    bidirectionalIndex.value[key].push({
      messageId,
      query,
      answer: answer.substring(0, 150) + (answer.length > 150 ? '…' : ''),
      timestamp: new Date().toLocaleTimeString(),
      source: chunk.source,
      page: chunk.page,
      text: chunk.text
    })
  })
}

const sendMessage = async (questionText) => {
  if (!questionText.trim()) return

  const userQuestion = questionText
  const userMsgIndex = messages.value.length

  messages.value.push({
    role: 'user',
    content: userQuestion,
    id: `msg_user_${Date.now()}_${userMsgIndex}`,
  })
  isLoading.value = true
  isRetrieving.value = true
  error.value = ''
  lastRetrievedChunks.value = []
  let timeoutId = null

  try {
    const documentStore = useDocumentStore()
    const payload = { query: userQuestion }
    const selectedSources = documentStore.selectedDocIds

    if (selectedSources && selectedSources.length > 0) {
      payload.sources = selectedSources
    }

    const controller = new AbortController()
    activeController = controller
    timeoutId = setTimeout(() => controller.abort(), 90000)
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || 'Failed to get response')
    }

    const data = await response.json()

    const sentences = data.sentences || []
    const sources = data.sources || {}
    const chunks = data.retrieved_chunks || []
    const reasoning = data.reasoning || null
    const answerText = (data.answer || sentences.map(s => s.text).join(' ') || 'No answer received.').toString()

    messages.value.push({
      role: 'assistant',
      content: answerText,
      reasoning: reasoning,
      sentences: sentences,
      sources: sources,
      chunks: chunks,
      id: `msg_${Date.now()}`
    })

    registerCitations(messages.value[messages.value.length - 1].id, userQuestion, answerText, chunks)
    lastRetrievedChunks.value = chunks
  } catch (err) {
    if (err.name === 'AbortError') {
      error.value = 'Request timed out. Please try again with a shorter question.'
    } else {
      error.value = err.message
    }
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    activeController = null
    isLoading.value = false
    isRetrieving.value = false
  }
}

const handleChunkClick = (chunk) => {
  if (chunk.source) {
    currentPdfUrl.value = '/media/data_source/' + encodeURIComponent(chunk.source)
    currentPdfPage.value = chunk.page || 1
    currentHighlightText.value = chunk.text?.substring(0, 50) || ''
    showPdfViewer.value = true
  }
}

const handleChunkRightClick = (event, chunk) => {
  event.preventDefault()
  const key = `${chunk.source}_${chunk.page}_${(chunk.text || '').substring(0, 50)}`
  const citations = bidirectionalIndex.value[key] || []
  if (citations.length > 0) {
    selectedCitation.value = {
      source: chunk.source,
      page: chunk.page,
      text: chunk.text
    }
    showBidirectionalPanel.value = true
  }
}

const closePdfViewer = () => {
  showPdfViewer.value = false
  currentPdfUrl.value = ''
  currentPdfPage.value = 1
  currentHighlightText.value = ''
}

const closeBidirectionalPanel = () => {
  showBidirectionalPanel.value = false
  selectedCitation.value = { source: '', page: null, text: '' }
}

const navigateToMessage = (messageId) => {
  setTimeout(() => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      element.style.animation = 'none'
      element.offsetHeight
      element.style.animation = 'highlightMessage 1s ease'
    }
  }, 100)
}

export function useChatState() {
  const documentStore = useDocumentStore()

  onMounted(loadMessages)
  watch(messages, saveMessages, { deep: true })

  onBeforeUnmount(() => {
    if (activeController) {
      activeController.abort()
      activeController = null
    }
  })

  return {
    messages,
    isLoading,
    error,
    lastRetrievedChunks,
    isRetrieving,
    showPdfViewer,
    currentPdfUrl,
    currentPdfPage,
    currentHighlightText,
    showBidirectionalPanel,
    selectedCitation,
    bidirectionalIndex,
    selectedSources: computed(() => documentStore.selectedDocIds),
    selectedCount: computed(() => documentStore.selectedCount),
    selectedDocuments: computed(() => documentStore.selectedDocuments),
    hasSelection: computed(() => documentStore.hasSelection),
    sendMessage,
    handleChunkClick,
    handleChunkRightClick,
    closePdfViewer,
    closeBidirectionalPanel,
    navigateToMessage,
  }
}
