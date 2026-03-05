import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const uploadPDF = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    },
  })
  
  return response.data
}

export const askQuestion = async (question) => {
  const response = await api.post('/chat', { query: question })
  return response.data
}

export const getSettings = async () => {
  const response = await api.get('/settings')
  return response.data
}

export const saveSettings = async (settings) => {
  const response = await api.post('/settings', {
    provider: settings.llm_provider,
    model: settings.model,
    api_key: settings.api_key,
  })
  return response.data
}

export const getRagConfig = async () => {
  const response = await api.get('/rag-config')
  return response.data
}

export const updateRagConfig = async (config) => {
  const response = await api.post('/rag-config/update', config)
  return response.data
}

export const resetIndex = async () => {
  const response = await api.post('/index/reset')
  return response.data
}

export const getFiles = async () => {
  const response = await api.get('/files')
  return response.data
}

export const deleteFile = async (filename) => {
  const response = await api.post('/documents/delete', { filename })
  return response.data
}

export default api
