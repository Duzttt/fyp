import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  createSummaryJob,
  getSummaryJobs,
  getSummaryJob,
  cancelSummaryJob,
  retrySummaryJob,
  deleteSummaryJob,
  getSummaryJobEventUrl,
} from '../services/api'

const TERMINAL = ['completed', 'failed', 'cancelled', 'interrupted']

export const useSummaryStore = defineStore('summary', () => {
  // State
  const job = ref(null)
  const history = ref([])
  const partialSections = ref([])
  const isLoading = ref(false)
  const error = ref(null)
  const lastEventId = ref('')

  let eventSource = null
  let reloadTimeout = null

  // Actions
  async function createJob(documentId, config = {}) {
    try {
      isLoading.value = true
      error.value = null
      partialSections.value = []
      const response = await createSummaryJob(documentId, config)
      job.value = response.job
      connectEvents()
      return job.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to create summary job:', err)
      return null
    } finally {
      isLoading.value = false
    }
  }

  function connectEvents() {
    if (!job.value?.id) return
    disconnect()
    eventSource = new EventSource(getSummaryJobEventUrl(job.value.id))

    eventSource.onmessage = (event) => handleEvent(JSON.parse(event.data))

    const handleNamed = (type) => {
      eventSource.addEventListener(type, (event) => {
        handleEvent(JSON.parse(event.data), type)
      })
    }
    handleNamed('stage')
    handleNamed('partial')
    handleNamed('completed')
    handleNamed('failed')
    handleNamed('cancelled')

    eventSource.onerror = () => {
      // EventSource auto-reconnects with Last-Event-ID; only hard-fail
      // if the job is unknown (e.g. deleted). Re-hydrate on terminal error.
      clearTimeout(reloadTimeout)
      reloadTimeout = setTimeout(async () => {
        reloadTimeout = null
        if (!job.value?.id) return
        try {
          await loadJob(job.value.id)
        } catch {
          /* keep existing state */
        }
      }, 2000)
    }
  }

  function handleEvent(payload, type) {
    if (!payload) return
    if (eventSource?.lastEventId) lastEventId.value = eventSource.lastEventId

    if (type === 'stage') {
      if (!job.value) return
      job.value.stage = payload.stage || job.value.stage
      job.value.progress = payload.progress ?? job.value.progress
      if (payload.topics) job.value.topics = payload.topics
      if (payload.language) job.value.detected_language = payload.language
    } else if (type === 'partial') {
      if (payload.section) partialSections.value.push(payload.section)
      if (!job.value) return
      job.value.progress = payload.progress ?? job.value.progress
    } else if (type === 'completed') {
      if (job.value) {
        job.value.status = 'completed'
        job.value.progress = 100
        job.value.result_markdown = payload.summary
      }
      hydrate()
      if (reloadTimeout) {
        clearTimeout(reloadTimeout)
        reloadTimeout = null
      }
      disconnect()
    } else if (type === 'failed' || type === 'cancelled') {
      if (job.value) {
        job.value.status = type
        job.value.error_code = payload.error_code
        job.value.error_message = payload.error_message
      }
      hydrate()
      if (reloadTimeout) {
        clearTimeout(reloadTimeout)
        reloadTimeout = null
      }
      disconnect()
    }
  }

  async function hydrate() {
    if (!job.value?.id) return
    try {
      const response = await getSummaryJob(job.value.id)
      job.value = response.job
      await loadHistory(20)
    } catch (err) {
      console.error('Failed to hydrate summary job:', err)
    }
  }

  function disconnect() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  async function loadJob(jobId) {
    try {
      isLoading.value = true
      error.value = null
      const response = await getSummaryJob(jobId)
      job.value = response.job
      partialSections.value = []
      if (job.value.result_json?.sections) {
        partialSections.value = job.value.result_json.sections
      }
      if (job.value.status && !TERMINAL.includes(job.value.status)) {
        connectEvents()
      }
      return job.value
    } catch (err) {
      error.value = err.message
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function loadHistory(limit = 20) {
    try {
      error.value = null
      const response = await getSummaryJobs(limit)
      history.value = response.jobs || []
    } catch (err) {
      error.value = err.message
      console.error('Failed to load summary history:', err)
    }
  }

  async function cancelActive() {
    if (!job.value?.id) return false
    try {
      await cancelSummaryJob(job.value.id)
      return true
    } catch (err) {
      error.value = err.message
      return false
    }
  }

  async function retryActive() {
    if (!job.value?.id) return false
    try {
      partialSections.value = []
      const response = await retrySummaryJob(job.value.id)
      job.value = response.job
      connectEvents()
      return true
    } catch (err) {
      error.value = err.message
      return false
    }
  }

  async function remove(jobId) {
    try {
      error.value = null
      await deleteSummaryJob(jobId)
      history.value = history.value.filter((item) => item.id !== jobId)
      if (job.value?.id === jobId) {
        disconnect()
        job.value = null
        partialSections.value = []
      }
      return true
    } catch (err) {
      error.value = err.message
      return false
    }
  }

  function reset() {
    disconnect()
    job.value = null
    partialSections.value = []
    error.value = null
  }

  return {
    job,
    history,
    partialSections,
    isLoading,
    error,
    lastEventId,
    createJob,
    connectEvents,
    disconnect,
    loadJob,
    loadHistory,
    cancelActive,
    retryActive,
    remove,
    reset,
  }
})
