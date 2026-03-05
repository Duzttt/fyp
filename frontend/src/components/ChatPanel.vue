<script setup>
import { ref } from 'vue'

const messages = ref([])
const question = ref('')
const isLoading = ref(false)
const error = ref('')

const sendMessage = async () => {
  if (!question.value.trim()) return
  
  const userQuestion = question.value
  messages.value.push({ role: 'user', content: userQuestion })
  question.value = ''
  isLoading.value = true
  error.value = ''
  
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: userQuestion }),
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || 'Failed to get response')
    }
    
    const data = await response.json()
    messages.value.push({ role: 'assistant', content: data.answer || data.response || 'No answer received.' })
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
  }
}

const handleKeyPress = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="panel chat-panel">
    <div class="chat-header">
      <div class="chat-title">
        <span class="chat-title-main">Chat</span>
        <span class="chat-title-sub">Ask anything about your notes</span>
      </div>
    </div>
    <div class="chat-body">
      <div v-if="messages.length === 0" class="chat-empty-card">
        <div class="chat-empty-icon">💬</div>
        <div class="chat-empty-title">Start a Conversation</div>
        <div class="chat-empty-desc">Ask questions about your lecture notes</div>
      </div>
      <div v-else class="messages-list">
        <div 
          v-for="(msg, idx) in messages" 
          :key="idx" 
          class="message"
          :class="msg.role"
        >
          <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="message-content">{{ msg.content }}</div>
        </div>
        <div v-if="isLoading" class="message assistant">
          <div class="message-avatar">🤖</div>
          <div class="message-content loading">Thinking...</div>
        </div>
      </div>
    </div>
    <div class="chat-input-wrap">
      <input
        v-model="question"
        @keydown.enter.prevent="sendMessage"
        type="text"
        class="chat-input"
        placeholder="Ask a question..."
        :disabled="isLoading"
      />
      <button 
        class="chat-send-btn" 
        @click="sendMessage"
        :disabled="isLoading || !question.trim()"
      >
        ➤
      </button>
    </div>
    <div v-if="error" class="chat-error">{{ error }}</div>
  </div>
</template>

<style scoped>
.chat-panel {
  position: relative;
  background: linear-gradient(
    135deg,
    rgba(15, 25, 45, 0.4) 0%,
    rgba(25, 35, 60, 0.5) 100%
  );
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-top-color: rgba(255, 255, 255, 0.12);
  border-left-color: rgba(255, 255, 255, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  backdrop-filter: blur(15px) saturate(180%);
  -webkit-backdrop-filter: blur(15px) saturate(180%);
  box-shadow:
    0 15px 30px -15px rgba(0, 0, 0, 0.6),
    inset 0 1px 1px rgba(255, 255, 255, 0.1),
    inset 0 -2px 2px rgba(0, 0, 0, 0.2);
}

.chat-header {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-main {
  font-size: 13px;
  font-weight: 600;
}

.chat-title-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.chat-body {
  flex: 1;
  padding: 14px;
  overflow-y: auto;
  position: relative;
  max-height: calc(100vh - 220px);
}

.chat-empty-card {
  margin: 0 auto;
  margin-top: 10%;
  max-width: 260px;
  text-align: center;
  padding: 16px 14px 18px;
  border-radius: 18px;
  background: linear-gradient(
    145deg,
    rgba(25, 35, 55, 0.5) 0%,
    rgba(15, 25, 45, 0.6) 100%
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-top-color: rgba(255, 255, 255, 0.2);
  border-left-color: rgba(255, 255, 255, 0.2);
  box-shadow:
    0 25px 40px -20px black,
    inset -2px -2px 5px rgba(0, 0, 0, 0.3),
    inset 2px 2px 5px rgba(255, 255, 255, 0.1);
}

.chat-empty-icon {
  width: 40px;
  height: 40px;
  border-radius: 16px;
  margin: 0 auto 10px;
  background: radial-gradient(circle at 20% 0, #a855f7, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #020617;
  font-size: 20px;
}

.chat-empty-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.chat-empty-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.3);
  margin-left: auto;
}

.message.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
}

.message-content.loading {
  color: var(--text-muted);
  font-style: italic;
}

.chat-input-wrap {
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  gap: 8px;
  align-items: center;
}

.chat-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: #020617;
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}

.chat-input:focus {
  border-color: var(--accent);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: linear-gradient(
    145deg,
    rgba(99, 102, 241, 0.8) 0%,
    rgba(139, 92, 246, 0.9) 100%
  );
  color: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 5px 15px -5px rgba(99, 102, 241, 0.3),
    inset 0 1px 2px rgba(255, 255, 255, 0.3);
  transition: all 0.2s ease;
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow:
    0 8px 20px -5px rgba(99, 102, 241, 0.5),
    inset 0 1px 3px rgba(255, 255, 255, 0.4);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.chat-error {
  margin: 4px 14px 0;
  min-height: 1.2em;
  font-size: 11px;
  color: #fca5a5;
}
</style>
