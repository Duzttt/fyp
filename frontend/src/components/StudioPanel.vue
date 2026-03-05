<script setup>
const studioOptions = [
  { id: 1, title: 'Summarize', sub: 'Generate summary' },
  { id: 2, title: 'Quiz', sub: 'Create quiz' },
  { id: 3, title: 'Flashcards', sub: 'Study cards' },
  { id: 4, title: 'Podcast', sub: 'Audio notes' },
]
</script>

<template>
  <div class="panel studio-panel">
    <div class="panel-header">
      <div>
        <span class="panel-header-title">Studio</span>
        <span class="panel-header-sub">AI Tools</span>
      </div>
    </div>
    <div class="studio-body">
      <div class="studio-grid">
        <div 
          v-for="option in studioOptions" 
          :key="option.id" 
          class="studio-card"
        >
          <span class="title">{{ option.title }}</span>
          <span class="sub">{{ option.sub }}</span>
        </div>
      </div>
      <div class="studio-footer">
        More tools coming soon...
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio-panel {
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
  transition: all 0.3s ease;
}

.studio-panel:hover {
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow:
    0 20px 40px -15px rgba(0, 0, 0, 0.7),
    inset 0 1px 2px rgba(255, 255, 255, 0.15);
}

.panel-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.panel-header-title {
  font-weight: 600;
}

.panel-header-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.studio-body {
  padding: calc(var(--spacing-unit) + 2px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.studio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.studio-card {
  padding: 9px 8px;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: #020617;
  display: flex;
  flex-direction: column;
  gap: 3px;
  cursor: pointer;
  transition: transform 0.1s ease-out, border-color 0.1s ease-out,
    box-shadow 0.1s ease-out;
}

.studio-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.8);
}

.studio-card span.title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
}

.studio-card span.sub {
  font-size: 10px;
  color: var(--text-muted);
}

.studio-footer {
  margin-top: 10px;
  padding: 8px 8px 10px;
  border-radius: 10px;
  border: 1px dashed rgba(55, 65, 81, 0.9);
  background: rgba(15, 23, 42, 0.6);
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}
</style>
