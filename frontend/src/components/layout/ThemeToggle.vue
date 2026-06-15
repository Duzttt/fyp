<script setup>
import { useThemeStore } from '../../composables/useThemeStore'

const { theme, cycleTheme } = useThemeStore()

const themeLabels = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
}

const themeIcons = {
  system: 'M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z',
  light: 'M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.42 0-.39.39-.39 1.03 0 1.42l1.06 1.06c.39.39 1.03.39 1.42 0s.39-1.03 0-1.42L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.42 0-.39.39-.39 1.03 0 1.42l1.06 1.06c.39.39 1.03.39 1.42 0 .39-.39.39-1.03 0-1.42l-1.06-1.06zm1.06-10.96c.39-.39.39-1.03 0-1.42-.39-.39-1.03-.39-1.42 0l-1.06 1.06c-.39.39-.39 1.03 0 1.42s1.03.39 1.42 0l1.06-1.06zM7.05 18.36c.39-.39.39-1.03 0-1.42-.39-.39-1.03-.39-1.42 0l-1.06 1.06c-.39.39-.39 1.03 0 1.42s1.03.39 1.42 0l1.06-1.06z',
  dark: 'M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z',
}

function getIconPath() {
  return themeIcons[theme.value]
}
</script>

<template>
  <button
    type="button"
    class="theme-toggle"
    :aria-label="`Switch theme (current: ${themeLabels[theme]})`"
    :title="`Theme: ${themeLabels[theme]}`"
    @click="cycleTheme"
  >
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path :d="getIconPath()" />
    </svg>
  </button>
</template>

<style scoped>
.theme-toggle {
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

.theme-toggle:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.theme-toggle svg {
  width: 18px;
  height: 18px;
}

.theme-toggle:hover,
.theme-toggle:active {
  background: rgba(99, 102, 241, 0.1);
  color: var(--on-surface);
}
</style>
