<script setup>
import { ref } from 'vue'
import RetrievalScopeIndicator from './RetrievalScopeIndicator.vue'

const props = defineProps({
  hasSelection: Boolean,
  selectedCount: Number,
  selectedDocuments: Array,
  hasMessages: Boolean
})

const emit = defineEmits(['clear'])

const showDocumentListTooltip = ref(false)

const toggleDocumentListTooltip = () => {
  showDocumentListTooltip.value = !showDocumentListTooltip.value
}
</script>

<template>
  <div class="chat-header">
    <div class="chat-title">
      <h2 class="chat-title-main">Chat</h2>
      <span class="chat-title-sub">Ask anything about your notes</span>
    </div>

    <div class="chat-header-right">
      <button
        v-if="hasMessages"
        type="button"
        class="clear-btn"
        title="Clear conversation"
        aria-label="Clear conversation"
        @click="emit('clear')"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/>
        </svg>
      </button>
      <RetrievalScopeIndicator
        :has-selection="hasSelection"
        :selected-count="selectedCount"
        :selected-documents="selectedDocuments"
        :show-tooltip="showDocumentListTooltip"
        @toggle-tooltip="toggleDocumentListTooltip"
        @close-tooltip="showDocumentListTooltip = false"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-header {
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--surface-container);
}

.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-main {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
}

.chat-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.clear-btn {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.clear-btn svg {
  width: 14px;
  height: 14px;
}

.clear-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.clear-btn:hover {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

.chat-title-sub {
  font-size: 12px;
  color: var(--on-surface-variant);
}
</style>
