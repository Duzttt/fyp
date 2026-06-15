<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  triggerRef: {
    type: Object,
    default: null,
  },
  offset: {
    type: Number,
    default: 10,
  },
  maxWidth: {
    type: Number,
    default: 320,
  },
})

const emit = defineEmits(['close'])

const tooltipRef = ref(null)
const position = ref({ x: 0, y: 0 })
const visible = ref(false)

const updatePosition = () => {
  const trigger = props.triggerRef
  if (!trigger) return

  const rect = trigger.getBoundingClientRect()
  const tooltipW = props.maxWidth
  const tooltipH = 200
  const offset = props.offset

  let x = rect.left + rect.width / 2 - tooltipW / 2
  let y = rect.bottom + offset

  if (x + tooltipW > window.innerWidth - 8) x = window.innerWidth - tooltipW - 8
  if (y + tooltipH > window.innerHeight - 8) y = rect.top - tooltipH - offset
  if (x < 8) x = 8
  if (y < 8) y = 8

  position.value = { x, y }
}

watch(
  () => props.show,
  (showing) => {
    if (showing) {
      updatePosition()
      visible.value = true
      document.addEventListener('click', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    } else {
      visible.value = false
      document.removeEventListener('click', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }
)

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleEscape)
})

const handleClickOutside = (e) => {
  if (tooltipRef.value && !tooltipRef.value.contains(e.target)) {
    emit('close')
  }
}

const handleEscape = (e) => {
  if (e.key === 'Escape') {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <transition name="base-tooltip-fade">
      <div
        v-if="show && visible"
        ref="tooltipRef"
        class="base-tooltip"
        :style="{
          left: `${position.x}px`,
          top: `${position.y}px`,
          maxWidth: `${maxWidth}px`,
        }"
        @click.stop
      >
        <slot />
      </div>
    </transition>
  </Teleport>
</template>

<style>
.base-tooltip {
  position: fixed;
  z-index: 10000;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
  padding: 12px;
  pointer-events: auto;
}

.base-tooltip-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 11px;
  font-weight: 600;
  color: white;
}

.base-tooltip-content {
  font-size: 12px;
  line-height: 1.6;
  color: white;
  max-height: 200px;
  overflow-y: auto;
}

.base-tooltip-content::-webkit-scrollbar {
  width: 4px;
}

.base-tooltip-content::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
}

.base-tooltip-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}

.base-tooltip-fade-enter-active,
.base-tooltip-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.base-tooltip-fade-enter-from,
.base-tooltip-fade-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}
</style>
