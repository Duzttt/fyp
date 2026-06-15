<script setup>
import { ICONS } from '../../constants/icons'
import ThemeToggle from './ThemeToggle.vue'

const emit = defineEmits(['open-admin', 'open-chunkviz', 'open-llm-config', 'open-rag-demo'])
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="brand">
        <div class="brand-icon">
          <span class="brand-icon-inner"></span>
        </div>
        <div class="brand-text">
          <span class="brand-title">The Academic Curator</span>
        </div>
      </div>
    </div>

    <div class="topbar-right">
      <button
        type="button"
        class="icon-btn"
        aria-label="RAG demo"
        title="RAG demo"
        @click="emit('open-rag-demo')"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path :d="ICONS.ragDemo"/>
        </svg>
      </button>
      <button
        type="button"
        class="icon-btn"
        aria-label="Model configuration"
        @click="emit('open-llm-config')"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="ICONS.modelConfig"/></svg>
      </button>
      <button
        type="button"
        class="icon-btn"
        aria-label="Chunk visualization"
        @click="emit('open-chunkviz')"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="ICONS.chunkViz"/></svg>
      </button>
      <button
        type="button"
        class="icon-btn"
        aria-label="Admin dashboard"
        @click="emit('open-admin')"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="ICONS.admin"/></svg>
      </button>
      <ThemeToggle />
      <button
        type="button"
        class="icon-btn notification-btn"
        aria-label="Notifications"
        disabled
      >
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
        <span class="notification-dot" aria-hidden="true"></span>
      </button>
      <div class="avatar" aria-hidden="true">
        <span class="avatar-letter">A</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-container);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--outline-variant);
}

.topbar-left {
  display: flex;
  align-items: center;
  min-width: 200px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-icon-inner {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background: var(--surface);
}

.brand-title {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: var(--on-surface);
  letter-spacing: -0.01em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 200px;
  justify-content: flex-end;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}

.icon-btn:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.icon-btn svg {
  width: 18px;
  height: 18px;
}

.icon-btn:hover {
  background: var(--primary-container);
  color: var(--on-primary);
}

.notification-btn {
  position: relative;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--tertiary);
  border: 1.5px solid var(--surface-container-low);
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-container), var(--primary));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 6px;
}

.avatar-letter {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  color: white;
}

@media (max-width: 900px) {
  .brand-title {
    display: none;
  }
}
</style>
