<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  stage: {
    type: Object,
    required: true,
  },
  index: {
    type: Number,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
  played: {
    type: Boolean,
    default: false,
  },
  technicalView: {
    type: Boolean,
    default: false,
  },
  maxDuration: {
    type: Number,
    default: 1,
  },
})

const emit = defineEmits(['stage-el'])

const showJson = ref(false)

const statusMeta = {
  completed: { icon: '✓', label: 'Completed', color: '#22c55e' },
  active: { icon: '⟳', label: 'Running', color: '#818cf8' },
  pending: { icon: '○', label: 'Pending', color: '#908f9e' },
  failed: { icon: '✕', label: 'Failed', color: '#ef4444' },
  skipped: { icon: '→', label: 'Skipped', color: '#a8a29e' },
}

const meta = computed(() => statusMeta[props.stage.status] || statusMeta.pending)
const results = computed(() => props.stage.results || [])
const hasJson = computed(() => Boolean(props.stage.details || props.stage.technical))
const durationMs = computed(() => Number(props.stage.duration_ms || 0))
const durationRatio = computed(() => {
  if (!durationMs.value || !props.maxDuration) return 0
  return Math.min(durationMs.value / props.maxDuration, 1)
})

const scoreColor = (score) => {
  if (score >= 0.8) return '#22c55e'
  if (score >= 0.5) return '#eab308'
  return '#ef4444'
}

const formatJson = (value) => JSON.stringify(value, null, 2)

const stageRefCb = (index) => (el) => {
  if (el) emit('stage-el', el, index)
}
</script>

<template>
  <article
    class="stage-card"
    :class="[`status-${stage.status}`, { active, played }]"
    :ref="stageRefCb(index)"
  >
    <div class="stage-rail">
      <span
        class="stage-dot"
        :style="{ borderColor: meta.color, color: meta.color, background: `${meta.color}1f` }"
      >
        <svg v-if="stage.status === 'completed'" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
        </svg>
        <svg v-else-if="stage.status === 'failed'" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
        </svg>
        <span v-else class="dot-number">{{ index + 1 }}</span>
      </span>
      <span v-if="stage.status !== 'completed' && stage.status !== 'failed'" class="dot-activity" />
    </div>

    <div class="stage-content">
      <div class="stage-head">
        <div class="stage-title-wrap">
          <h3 class="stage-title">{{ stage.title }}</h3>
          <span class="stage-status" :style="{ color: meta.color }">{{ meta.label }}</span>
        </div>
        <span v-if="durationMs > 0" class="stage-duration">{{ durationMs }}ms</span>
      </div>

      <div v-if="durationRatio > 0" class="duration-track" aria-hidden="true">
        <span class="duration-fill" :style="{ width: `${durationRatio * 100}%` }" />
      </div>

      <p class="stage-summary">{{ stage.summary }}</p>

      <div v-if="results.length" class="stage-results">
        <div
          v-for="item in results"
          :key="`${stage.id}-${item.rank || item.id || item.source}`"
          class="result-item"
        >
          <div class="result-meta">
            <span v-if="item.rank" class="rank-badge">#{{ item.rank }}</span>
            <span v-if="item.source" class="result-source">{{ item.source }}</span>
            <span v-if="item.page" class="result-page">p.{{ item.page }}</span>
            <span v-if="item.score !== undefined" class="score-label">score {{ item.score }}</span>
          </div>
          <div v-if="item.score !== undefined" class="score-track" aria-hidden="true">
            <span
              class="score-fill"
              :style="{ width: `${Math.min(Math.max(item.score, 0), 1) * 100}%`, background: scoreColor(item.score) }"
            />
          </div>
          <p class="result-preview">{{ item.preview || item.text || item.id }}</p>
        </div>
      </div>

      <div v-if="stage.error" class="stage-error" role="alert">
        <strong>Error</strong>
        <span>{{ stage.error }}</span>
      </div>

      <div v-if="technicalView && hasJson" class="json-block">
        <button
          type="button"
          class="json-toggle"
          :aria-expanded="showJson"
          @click="showJson = !showJson"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path :d="showJson ? 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z' : 'M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z'" />
          </svg>
          {{ showJson ? 'Hide technical data' : 'Show technical data' }}
        </button>
        <pre v-if="showJson" class="json-pre">{{ formatJson({ details: stage.details, technical: stage.technical }) }}</pre>
      </div>
    </div>
  </article>
</template>

<style scoped>
.stage-card {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
  transition: border-color 0.25s, box-shadow 0.25s, background-color 0.25s;
  opacity: 0.55;
}

.stage-card.played {
  opacity: 0.85;
}

.stage-card.active {
  opacity: 1;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15), 0 12px 32px -12px rgba(0, 0, 0, 0.4);
}

.stage-card.status-failed {
  border-color: rgba(239, 68, 68, 0.4);
}

.stage-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  gap: 6px;
}

.stage-dot {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 2px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  transition: transform 0.25s;
}

.stage-card.active .stage-dot {
  transform: scale(1.12);
}

.stage-dot svg {
  width: 16px;
  height: 16px;
}

.dot-number {
  font-size: 12px;
}

.dot-activity {
  width: 2px;
  flex: 1;
  min-height: 24px;
  background: var(--outline-variant);
  border-radius: 1px;
}

.stage-card:last-child .dot-activity {
  display: none;
}

.stage-card.active .dot-activity {
  background: linear-gradient(180deg, var(--accent), transparent);
  animation: pulse 1.2s ease-in-out infinite;
}

.stage-content {
  flex: 1;
  min-width: 0;
}

.stage-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.stage-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.stage-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}

.stage-status {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  flex-shrink: 0;
}

.stage-duration {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.duration-track {
  height: 3px;
  border-radius: 2px;
  background: var(--surface-container-high);
  overflow: hidden;
  margin-bottom: 10px;
}

.duration-fill {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  transition: width 0.4s ease;
}

.stage-summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}

.stage-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.result-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-container);
  border: 1px solid var(--outline-variant);
}

.result-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.rank-badge {
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  color: var(--accent);
  font-size: 10px;
  font-weight: 700;
}

.result-source {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

.result-page {
  font-size: 10px;
  color: var(--text-muted);
}

.score-label {
  margin-left: auto;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.score-track {
  height: 5px;
  border-radius: 3px;
  background: var(--surface-container-high);
  overflow: hidden;
  margin-bottom: 8px;
}

.score-fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.result-preview {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-muted);
}

.stage-error {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stage-error strong {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.json-block {
  margin-top: 12px;
}

.json-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px dashed var(--outline-variant);
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.json-toggle:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.json-toggle svg {
  width: 12px;
  height: 12px;
}

.json-pre {
  margin: 8px 0 0;
  padding: 12px;
  border-radius: 10px;
  background: var(--surface-container-lowest);
  border: 1px solid rgba(129, 140, 248, 0.2);
  color: var(--text-main);
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}
</style>
