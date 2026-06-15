<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  isLoading: Boolean
})

const emit = defineEmits(['send'])

const question = ref('')
const textareaRef = ref(null)

const sendMessage = () => {
  if (!question.value.trim()) return
  emit('send', question.value)
  question.value = ''
  nextTick(resizeTextarea)
}

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

const resizeTextarea = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<template>
  <div class="chat-input-wrap">
    <label class="sr-only" for="chat-question-input">Your question</label>
    <textarea
      id="chat-question-input"
      ref="textareaRef"
      v-model="question"
      @keydown="handleKeydown"
      @input="resizeTextarea"
      class="chat-input"
      name="question"
      autocomplete="off"
      placeholder="Ask a question… (Shift+Enter for newline)"
      :disabled="isLoading"
      rows="1"
      maxlength="4000"
    ></textarea>
    <button
      type="button"
      class="chat-send-btn"
      aria-label="Send message"
      @click="sendMessage"
      :disabled="isLoading || !question.trim()"
    >
      <svg v-if="isLoading" class="send-spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
      </svg>
      <svg v-else viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
    </button>
  </div>
</template>

<style scoped>
.chat-input-wrap {
  padding: 12px 16px 16px;
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: var(--surface-container);
  border-top: 1px solid rgba(69, 70, 83, 0.15);
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

.chat-input {
  flex: 1;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid rgba(69, 70, 83, 0.15);
  background: var(--surface-container-lowest);
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  overflow-y: auto;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-input:focus {
  outline: none;
}

.chat-input:focus-visible {
  outline: none;
  border-color: var(--primary-container);
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.35);
}

.chat-input::placeholder {
  color: var(--on-surface-variant);
  opacity: 0.5;
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  color: var(--on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  flex-shrink: 0;
}

.chat-send-btn:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.chat-send-btn svg {
  width: 18px;
  height: 18px;
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 16px rgba(129, 140, 248, 0.3);
}

.chat-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.send-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}
</style>
