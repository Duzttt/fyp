const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const uploadPDF = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload PDF');
  }

  return response.json();
};

export const getUploadStatus = async () => {
  const response = await fetch(`${API_BASE_URL}/api/upload/status`);
  if (!response.ok) {
    throw new Error('Failed to check upload status');
  }
  return response.json();
};

export const askQuestion = async (question, sources = null) => {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: question, sources }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get answer');
  }

  return response.json();
};

export const checkHealth = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
};

export const getSettings = async () => {
  const response = await fetch(`${API_BASE_URL}/api/settings`);
  if (!response.ok) {
    throw new Error('Failed to get settings');
  }
  return response.json();
};

export const updateSettings = async (settings) => {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update settings');
  }

  return response.json();
};

export const listFiles = async () => {
  const response = await fetch(`${API_BASE_URL}/api/files`);
  if (!response.ok) {
    throw new Error('Failed to list files');
  }
  return response.json();
};

export const summarizeDoc = async (filename) => {
  const response = await fetch(`${API_BASE_URL}/api/summarize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ filename }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to summarize document');
  }

  return response.json();
};

export const generatePodcast = async (filename) => {
  const response = await fetch(`${API_BASE_URL}/api/podcast`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ filename }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to generate podcast');
  }

  return response.json();
};
