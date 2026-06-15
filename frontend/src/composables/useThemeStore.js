import { ref, computed } from 'vue'

const STORAGE_KEY = 'theme-preference'
const VALID_THEMES = ['system', 'light', 'dark']

const theme = ref('system')
const appliedTheme = ref(null)

const osPreference = ref('dark')

function detectOSPreference() {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function resolveTheme(mode) {
  if (mode === 'system') {
    return osPreference.value
  }
  return mode
}

function applyToDOM(resolved) {
  document.documentElement.setAttribute('data-theme', resolved)
  appliedTheme.value = resolved
}

function saveToStorage(mode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch (e) {
    // localStorage unavailable
  }
}

function readFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && VALID_THEMES.includes(stored)) {
      return stored
    }
  } catch (e) {
    // localStorage unavailable
  }
  return 'system'
}

function setTheme(mode) {
  if (!VALID_THEMES.includes(mode)) return
  theme.value = mode
  saveToStorage(mode)
  applyToDOM(resolveTheme(mode))
}

function cycleTheme() {
  const currentIndex = VALID_THEMES.indexOf(theme.value)
  const nextIndex = (currentIndex + 1) % VALID_THEMES.length
  setTheme(VALID_THEMES[nextIndex])
}

function initTheme() {
  osPreference.value = detectOSPreference()
  const stored = readFromStorage()
  theme.value = stored
  applyToDOM(resolveTheme(stored))
}

let mediaQuery = null
let mediaHandler = null

function startListening() {
  if (!window.matchMedia) return
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaHandler = (e) => {
    osPreference.value = e.matches ? 'dark' : 'light'
    if (theme.value === 'system') {
      applyToDOM(resolveTheme('system'))
    }
  }
  mediaQuery.addEventListener('change', mediaHandler)
}

function stopListening() {
  if (mediaQuery && mediaHandler) {
    mediaQuery.removeEventListener('change', mediaHandler)
    mediaQuery = null
    mediaHandler = null
  }
}

function handleStorageEvent(e) {
  if (e.key === STORAGE_KEY && e.newValue && VALID_THEMES.includes(e.newValue)) {
    theme.value = e.newValue
    applyToDOM(resolveTheme(e.newValue))
  }
}

export function useThemeStore() {
  return {
    theme: computed(() => theme.value),
    appliedTheme: computed(() => appliedTheme.value),
    setTheme,
    cycleTheme,
    initTheme,
    startListening,
    stopListening,
    handleStorageEvent,
  }
}
