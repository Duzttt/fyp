<script setup>
import { ref, computed } from 'vue'
import CitationAnswer from './CitationAnswer.vue'
import MarkdownRenderer from '../shared/MarkdownRenderer.vue'

const props = defineProps({
  message: Object
})

const showReasoning = ref(false)
const copied = ref(false)

const copyAnswer = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content || '')
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (_) {
    // clipboard unavailable — ignore
  }
}

const toggleReasoning = () => {
  showReasoning.value = !showReasoning.value
}

const formatDuration = (ms) => {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const citationTitle = computed(() => {
  const msg = props.message
  if (!msg || msg.role !== 'assistant' || !msg.chunks || !msg.chunks.length) {
    return ''
  }
  const sources = Array.from(
    new Set(
      msg.chunks
        .map((c) => c.source)
        .filter((s) => typeof s === 'string' && s.trim()),
    ),
  )
  if (!sources.length) return ''
  return `Supported by: ${sources.join(', ')}`
})
</script>

<template>
  <div class="message" :class="message.role">
    <div class="message-avatar" aria-hidden="true">
      <svg v-if="message.role === 'user'" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
      <svg v-else viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/></svg>
    </div>
    <span class="sr-only">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
    <div
      class="message-content"
      :class="{
        'has-citations': message.role === 'assistant' && message.chunks && message.chunks.length > 0
      }"
      :title="citationTitle"
    >
      <button
        v-if="message.role === 'assistant' && !message.stopped"
        type="button"
        class="copy-btn"
        :aria-label="copied ? 'Copied to clipboard' : 'Copy answer'"
        :title="copied ? 'Copied!' : 'Copy answer'"
        @click="copyAnswer"
      >
        <svg v-if="copied" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
      <!-- Reasoning/Thinking Section (Collapsible) -->
      <div v-if="message.reasoning" class="reasoning-section">
        <button 
          class="reasoning-toggle" 
          @click="toggleReasoning"
          :aria-expanded="showReasoning"
          :aria-controls="`reasoning-content-${message.id}`"
        >
          <span class="reasoning-icon" :class="{ 'is-open': showReasoning }">
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4.5L6 7.5l3-3"/></svg>
          </span>
          <span class="reasoning-label">
            {{ showReasoning ? 'Hide' : 'Show' }} thinking process
          </span>
          <span class="reasoning-badge">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 1.5a4 4 0 0 1 2.5 7.1c-.5.4-.8 1-.8 1.65H6.3c0-.65-.3-1.25-.8-1.65A4 4 0 0 1 8 1.5z"/><path d="M6.3 12h3.4M7 14h2"/></svg>
            Reasoning
            <span v-if="message.elapsedMs" class="reasoning-duration">{{ formatDuration(message.elapsedMs) }}</span>
          </span>
        </button>
        
        <transition name="reasoning-expand">
          <div v-show="showReasoning" :id="`reasoning-content-${message.id}`" class="reasoning-content">
            <MarkdownRenderer :content="message.reasoning" class="reasoning-markdown" />
          </div>
        </transition>
      </div>

      <!-- Answer Section -->
      <CitationAnswer
        v-if="message.role === 'assistant' && message.sentences && message.sentences.length > 0"
        :sentences="message.sentences"
        :sources="message.sources"
        :show-tooltip="true"
      />
      <MarkdownRenderer
        v-else-if="message.role === 'assistant'"
        :content="message.content"
        class="assistant-markdown"
      />
      <template v-else>
        {{ message.content }}
      </template>
    </div>
  </div>
</template>

<style scoped>
.message {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  background: var(--bubble-user-bg);
  border: 1px solid var(--bubble-user-border);
  margin-left: auto;
}

.message.assistant {
  align-self: flex-start;
  background: var(--bubble-assistant-bg);
  border: 1px solid var(--bubble-assistant-border);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.message-avatar svg {
  width: 18px;
  height: 18px;
  color: var(--primary-container);
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  flex: 1;
  min-width: 0;
  position: relative;
}

.copy-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-high);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity 0.2s, transform 0.2s, color 0.2s, border-color 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.copy-btn svg {
  width: 13px;
  height: 13px;
}

.message:hover .copy-btn,
.copy-btn:focus-visible {
  opacity: 1;
  transform: translateY(0);
}

.copy-btn:hover {
  color: var(--accent);
  border-color: rgba(99, 102, 241, 0.5);
}

.message-content.has-citations {
  position: relative;
}

/* Reasoning/Thinking Section */
.reasoning-section {
  margin-bottom: 12px;
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 8px;
  background: rgba(168, 85, 247, 0.05);
  overflow: hidden;
}

.reasoning-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(168, 85, 247, 0.1);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-main);
  transition: all 0.2s ease;
  text-align: left;
}

.reasoning-toggle:hover {
  background: rgba(168, 85, 247, 0.15);
}

.reasoning-toggle:active {
  background: rgba(168, 85, 247, 0.2);
}

.reasoning-icon {
  font-size: 10px;
  color: rgba(168, 85, 247, 0.8);
  transition: transform 0.2s ease;
  flex-shrink: 0;
  display: inline-flex;
}

.reasoning-icon svg {
  width: 12px;
  height: 12px;
}

.reasoning-icon.is-open {
  transform: rotate(180deg);
}

.reasoning-label {
  flex: 1;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.reasoning-badge {
  padding: 2px 8px;
  background: rgba(168, 85, 247, 0.2);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 12px;
  font-size: 10px;
  font-weight: 600;
  color: rgba(168, 85, 247, 0.9);
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.reasoning-badge svg {
  width: 12px;
  height: 12px;
}

.reasoning-duration {
  font-weight: 400;
  opacity: 0.7;
}

.reasoning-content {
  padding: 12px;
  background: var(--surface-container-low);
  border-top: 1px solid rgba(168, 85, 247, 0.2);
}

.reasoning-markdown {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-muted);
}

.reasoning-markdown :deep(code) {
  font-family: 'Courier New', Courier, monospace;
  background: var(--surface-container);
}

.reasoning-markdown :deep(pre) {
  background: var(--surface-container-high);
  border-left: 3px solid rgba(168, 85, 247, 0.4);
}

/* Reasoning expand animation */
.reasoning-expand-enter-active,
.reasoning-expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.reasoning-expand-enter-from,
.reasoning-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.reasoning-expand-enter-to,
.reasoning-expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}

/* Assistant Markdown Styling */
.assistant-markdown {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
}

.assistant-markdown :deep(h1),
.assistant-markdown :deep(h2),
.assistant-markdown :deep(h3),
.assistant-markdown :deep(h4),
.assistant-markdown :deep(h5),
.assistant-markdown :deep(h6) {
  color: var(--text-main);
}

.assistant-markdown :deep(ul),
.assistant-markdown :deep(ol) {
  margin: 8px 0;
}

.assistant-markdown :deep(li) {
  margin: 4px 0;
}

.assistant-markdown :deep(strong) {
  color: var(--text-main);
}

.assistant-markdown :deep(code) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(129, 140, 248, 0.1);
  color: rgba(129, 140, 248, 0.9);
}

.assistant-markdown :deep(pre) {
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--surface-container-low);
  border: 1px solid var(--outline-variant);
  overflow-x: auto;
}

.assistant-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 0.85em;
}

.assistant-markdown :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid rgba(129, 140, 248, 0.5);
  background: rgba(129, 140, 248, 0.05);
  border-radius: 0 8px 8px 0;
}

.assistant-markdown :deep(table) {
  margin: 12px 0;
  border-collapse: collapse;
  width: 100%;
}

.assistant-markdown :deep(th),
.assistant-markdown :deep(td) {
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.assistant-markdown :deep(th) {
  background: rgba(99, 102, 241, 0.1);
}

.assistant-markdown :deep(a) {
  color: var(--accent, #6366f1);
}
</style>
