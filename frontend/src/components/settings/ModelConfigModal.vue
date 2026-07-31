<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useLlmSettingsStore } from '../../stores/llmSettingsStore'
import { getRagConfig, updateRagConfig, saveSettings } from '../../services/api'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show'])

const llmStore = useLlmSettingsStore()

// Provider icons (Material-style 24x24)
const providerIcons = {
  gemini:
    'M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z',
  openrouter:
    'M12 2c1.66 0 3 1.34 3 3 0 .68-.22 1.3-.6 1.8l2.1 3.5c.5-.19 1.04-.3 1.6-.3 1.66 0 3 1.34 3 3s-1.34 3-3 3c-.56 0-1.1-.11-1.6-.3l-2.1 3.5c.38.5.6 1.12.6 1.8 0 1.66-1.34 3-3 3s-3-1.34-3-3c0-.68.22-1.3.6-1.8l-2.1-3.5c-.5.19-1.04.3-1.6.3-1.66 0-3-1.34-3-3s1.34-3 3-3c.56 0 1.1.11 1.6.3l2.1-3.5C9.22 5.3 9 4.68 9 4c0-1.66 1.34-3 3-3z',
  local_llm:
    'M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zM7.76 16.24l-1.41-1.41L8.59 13 6.35 10.76l1.41-1.41L11.41 13l-3.65 3.24zM16 16h-4v-2h4v2z',
}

// Form state
const selectedProvider = ref('')
const selectedModel = ref('')
const apiKey = ref('')
const showApiKey = ref(false)
const temperature = ref(0.7)
const topK = ref(3)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)
const saveMessage = ref('')
const error = ref('')

const providers = computed(() => llmStore.providers || [])

const currentProviderData = computed(() =>
  providers.value.find(p => p.id === selectedProvider.value) || null
)
const availableModels = computed(() => currentProviderData.value?.models || [])
const requiresApiKey = computed(() => currentProviderData.value?.requires_api_key ?? true)
const isLocal = computed(() => selectedProvider.value === 'local_llm')
const isCurrent = computed(
  () => selectedProvider.value === llmStore.currentProvider
    && selectedModel.value === llmStore.currentModel
)

const resetForm = () => {
  selectedProvider.value = llmStore.currentProvider || providers.value[0]?.id || ''
  selectedModel.value = llmStore.currentModel || ''
  apiKey.value = ''
  showApiKey.value = false
  testResult.value = null
  saveMessage.value = ''
  error.value = ''
}

const loadRagConfig = async () => {
  try {
    const cfg = await getRagConfig()
    temperature.value = cfg.temperature ?? 0.7
    topK.value = cfg.top_k ?? 3
  } catch (err) {
    console.error('Failed to load RAG config:', err)
  }
}

watch(() => props.show, async (show) => {
  if (!show) return
  try {
    await llmStore.loadProviders()
  } catch (err) {
    error.value = err.message
  }
  resetForm()
  await loadRagConfig()
})

const handleProviderSelect = (providerId) => {
  if (providerId === selectedProvider.value) return
  selectedProvider.value = providerId
  const p = providers.value.find(pr => pr.id === providerId)
  selectedModel.value = p?.models?.[0] || ''
  apiKey.value = ''
  testResult.value = null
  saveMessage.value = ''
}

const handleTest = async () => {
  if (!selectedProvider.value || !selectedModel.value.trim()) {
    error.value = 'Select a provider and model first'
    return
  }
  testing.value = true
  error.value = ''
  testResult.value = null
  try {
    const result = await llmStore.testConnection(selectedProvider.value, selectedModel.value.trim())
    testResult.value = {
      success: true,
      message: result.detail || 'Connection successful',
    }
  } catch (err) {
    testResult.value = {
      success: false,
      message: err.message || 'Connection failed',
    }
  } finally {
    testing.value = false
    testTimeout = setTimeout(() => { testResult.value = null }, 8000)
  }
}

const handleSave = async () => {
  if (!selectedProvider.value || !selectedModel.value.trim()) {
    error.value = 'Select a provider and model before saving'
    return
  }
  saving.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    // 1. Save provider + model. Keep the existing API key unless a new one was entered.
    const payload = {
      llm_provider: selectedProvider.value,
      model: selectedModel.value.trim(),
    }
    if (apiKey.value.trim()) payload.api_key = apiKey.value.trim()
    const settingsResp = await saveSettings(payload)
    if (!settingsResp.success) {
      throw new Error(settingsResp.detail || settingsResp.message || 'Failed to save settings')
    }

    // 2. Persist RAG generation parameters.
    await updateRagConfig({ top_k: Number(topK.value), temperature: Number(temperature.value) })

    // 3. Refresh store state so the rest of the app reflects the change.
    llmStore.currentProvider = selectedProvider.value
    llmStore.currentModel = selectedModel.value.trim()
    await llmStore.loadProviders()

    saveMessage.value = 'Configuration saved successfully'
    saveTimeout = setTimeout(() => {
      saveMessage.value = ''
      emit('update:show', false)
    }, 900)
  } catch (err) {
    error.value = err.message || 'Failed to save configuration'
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  emit('update:show', false)
}

let saveTimeout = null
let testTimeout = null

onBeforeUnmount(() => {
  if (saveTimeout) clearTimeout(saveTimeout)
  if (testTimeout) clearTimeout(testTimeout)
})
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="handleClose">
    <div class="modal-container">
      <div class="modal-header">
        <div class="modal-heading">
          <h3>Model Configuration</h3>
          <p class="modal-sub">Configure your LLM provider, model and generation parameters.</p>
        </div>
        <button type="button" class="modal-close" aria-label="Close" @click="handleClose">✕</button>
      </div>

      <div class="modal-body">
        <!-- Provider selection -->
        <div class="form-section">
          <span class="section-label">LLM Provider</span>
          <div class="provider-grid">
            <button
              v-for="provider in providers"
              :key="provider.id"
              type="button"
              class="provider-card"
              :class="{ active: selectedProvider === provider.id }"
              @click="handleProviderSelect(provider.id)"
            >
              <span class="provider-icon-wrap">
                <svg class="provider-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path :d="providerIcons[provider.id] || providerIcons.local_llm" />
                </svg>
              </span>
              <span class="provider-name">{{ provider.name }}</span>
              <span
                v-if="provider.id === llmStore.currentProvider"
                class="provider-tag current"
              >Active</span>
              <span
                v-else-if="provider.requires_api_key && !provider.has_api_key"
                class="provider-tag"
              >Key needed</span>
            </button>
          </div>
        </div>

        <!-- Model & credentials -->
        <div class="form-section">
          <span class="section-label">Model &amp; Credentials</span>

          <div class="form-row">
            <label class="form-label" for="model-select">Model</label>
            <div v-if="availableModels.length > 0" class="select-wrap">
              <select
                id="model-select"
                v-model="selectedModel"
                class="form-select"
                :disabled="isLocal && availableModels.length === 0"
              >
                <option v-for="model in availableModels" :key="model" :value="model">
                  {{ model }}
                </option>
              </select>
              <svg class="select-arrow" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M7 10l5 5 5-5z" />
              </svg>
            </div>
            <input
              v-else
              id="model-select"
              v-model="selectedModel"
              type="text"
              class="form-input"
              :placeholder="isLocal ? 'e.g., qwen2.5-3b-instruct-q4_k_m' : 'Enter model name'"
            />
          </div>

          <div v-if="requiresApiKey" class="form-row">
            <label class="form-label" for="api-key-input">API Key</label>
            <div class="api-key-wrap">
              <svg class="api-key-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
              </svg>
              <input
                id="api-key-input"
                v-model="apiKey"
                :type="showApiKey ? 'text' : 'password'"
                class="form-input api-key-input"
                placeholder="sk-..."
              />
              <button
                type="button"
                class="api-key-toggle"
                :aria-label="showApiKey ? 'Hide API key' : 'Show API key'"
                @click="showApiKey = !showApiKey"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path v-if="showApiKey" d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z" />
                  <path v-else d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
                </svg>
              </button>
            </div>
            <p class="form-hint">Leave blank to keep the existing key.</p>
          </div>

          <div v-else class="local-hint">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z" />
            </svg>
            Local LLM (llama.cpp) does not require an API key.
          </div>
        </div>

        <!-- Generation parameters -->
        <div class="form-section">
          <span class="section-label">Generation Parameters</span>

          <div class="param-row">
            <div class="param-label-row">
              <label class="form-label">Temperature</label>
              <span class="param-value">{{ temperature.toFixed(1) }}</span>
            </div>
            <input
              v-model.number="temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              class="form-range"
            />
            <div class="range-labels">
              <span>Precise</span>
              <span>Creative</span>
            </div>
          </div>

          <div class="param-row">
            <div class="param-label-row">
              <label class="form-label">Top K</label>
              <span class="param-value">{{ topK }}</span>
            </div>
            <input
              v-model.number="topK"
              type="range"
              min="1"
              max="10"
              step="1"
              class="form-range"
            />
            <div class="range-labels">
              <span>Narrow</span>
              <span>Broad</span>
            </div>
          </div>
        </div>

        <!-- Connection test -->
        <div class="form-section">
          <button
            type="button"
            class="test-btn"
            :disabled="testing || !selectedModel"
            @click="handleTest"
          >
            <svg v-if="testing" class="spin" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
            </svg>
            {{ testing ? 'Testing...' : 'Test Connection' }}
          </button>

          <div
            v-if="testResult"
            class="test-result"
            :class="testResult.success ? 'success' : 'error'"
            role="status"
          >
            {{ testResult.message }}
          </div>
        </div>

        <div v-if="error" class="settings-error" role="alert">{{ error }}</div>
        <div v-if="saveMessage" class="save-message" role="status">{{ saveMessage }}</div>
      </div>

      <div class="modal-footer">
        <span class="footer-note">Changes are applied immediately after saving.</span>
        <div class="modal-actions">
          <button type="button" class="modal-btn secondary" @click="handleClose">Cancel</button>
          <button
            type="button"
            class="modal-btn primary"
            :disabled="saving"
            @click="handleSave"
          >
            {{ saving ? 'Saving...' : 'Save Configuration' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

.modal-container {
  width: min(600px, 92vw);
  max-height: 88vh;
  background: var(--surface-container-high);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  box-shadow:
    0 30px 60px -20px rgba(0, 0, 0, 0.35),
    inset 0 1px 1px rgba(128, 128, 128, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.3s ease;
}

.modal-header {
  padding: 18px 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--outline-variant);
  background: var(--surface-container);
}

.modal-heading h3 {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-main);
}

.modal-sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.modal-close {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--outline-variant);
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.modal-close:hover {
  background: rgba(128, 128, 128, 0.2);
  color: var(--text-main);
  transform: rotate(90deg);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* Provider cards */
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.provider-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  color: var(--text-main);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
  position: relative;
}

.provider-card:hover {
  border-color: var(--outline);
  background: var(--surface-container);
}

.provider-card.active {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.12);
}

.provider-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.provider-icon-wrap {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.provider-icon {
  width: 16px;
  height: 16px;
  color: var(--accent);
}

.provider-name {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-tag {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-muted);
}

.provider-tag.current {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

/* Form rows */
.form-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.select-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.form-select {
  width: 100%;
  padding: 9px 34px 9px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  transition: border-color 0.15s;
}

.form-select:focus {
  border-color: var(--accent);
}

.select-arrow {
  position: absolute;
  right: 12px;
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  pointer-events: none;
}

.form-input {
  width: 100%;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-lowest);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.form-input:focus {
  border-color: var(--accent);
}

.api-key-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.api-key-icon {
  position: absolute;
  left: 12px;
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  pointer-events: none;
}

.api-key-input {
  padding-left: 34px;
  padding-right: 40px;
}

.api-key-toggle {
  position: absolute;
  right: 6px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.15s, color 0.15s;
}

.api-key-toggle:hover {
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-main);
}

.api-key-toggle svg {
  width: 15px;
  height: 15px;
}

.form-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.85;
}

.local-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(128, 128, 128, 0.08);
  border: 1px dashed var(--outline-variant);
  font-size: 12px;
  color: var(--text-muted);
}

.local-hint svg {
  width: 16px;
  height: 16px;
  color: var(--accent);
  flex-shrink: 0;
}

/* Parameter sliders */
.param-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.param-value {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  min-width: 28px;
  text-align: right;
}

.form-range {
  width: 100%;
  height: 5px;
  border-radius: 3px;
  background: var(--outline-variant);
  -webkit-appearance: none;
  appearance: none;
  outline: none;
}

.form-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--surface-container-lowest);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}

.form-range::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--surface-container-lowest);
  cursor: pointer;
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
}

/* Test connection */
.test-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 16px;
  border-radius: 10px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  color: var(--text-main);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  transition: all 0.15s;
}

.test-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-btn svg {
  width: 14px;
  height: 14px;
}

.spin {
  animation: spin 0.8s linear infinite;
}

.test-result {
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 12px;
}

.test-result.success {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #22c55e;
}

.test-result.error {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

.settings-error {
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
  font-size: 12px;
}

.save-message {
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #22c55e;
  font-size: 12px;
}

/* Footer */
.modal-footer {
  padding: 14px 24px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--outline-variant);
  background: var(--surface-container);
}

.footer-note {
  font-size: 11px;
  color: var(--text-muted);
}

.modal-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.modal-btn {
  padding: 8px 18px;
  border-radius: 30px;
  border: 1px solid var(--outline-variant);
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-main);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-btn.secondary:hover {
  background: rgba(128, 128, 128, 0.2);
}

.modal-btn.primary {
  background: linear-gradient(135deg, var(--accent), #a855f7);
  border: none;
  color: white;
  box-shadow: 0 10px 20px -10px var(--accent);
}

.modal-btn.primary:hover:not(:disabled) {
  transform: scale(1.04);
  filter: brightness(1.1);
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
