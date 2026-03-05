<script setup>
import Topbar from './components/Topbar.vue'
import SourcesPanel from './components/SourcesPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import StudioPanel from './components/StudioPanel.vue'
import SettingsModal from './components/SettingsModal.vue'
import { ref } from 'vue'

const showSettings = ref(false)
</script>

<template>
  <div class="app-shell">
    <Topbar @open-settings="showSettings = true" />
    <main class="main">
      <SourcesPanel />
      <ChatPanel />
      <StudioPanel />
    </main>
    <SettingsModal v-model:show="showSettings" />
  </div>
</template>

<style scoped>
.app-shell {
  width: min(1280px, 100vw);
  height: min(720px, 100vh - 40px);
  background: rgba(15, 23, 42, 0.95);
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.8);
}

.main {
  flex: 1;
  display: grid;
  grid-template-columns: 260px minmax(0, 1.4fr) 270px;
  gap: var(--spacing-unit);
  padding: calc(var(--spacing-unit) + 2px) var(--spacing-unit)
    calc(var(--spacing-unit) * 1.75);
  background: radial-gradient(circle at top, #020617 0, #020617 45%, #000 90%);
  min-width: 0;
}

@media (max-width: 1024px) {
  .app-shell {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
  }
}

@media (max-width: 900px) {
  .main {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
