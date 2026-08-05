# Light & Dark Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add light/dark mode toggle with system preference detection and localStorage persistence to the Vue.js frontend.

**Architecture:** Use CSS custom properties with `[data-theme]` selectors for theme switching. A Vue composable manages state and DOM updates. A toggle button in the topbar cycles through System/Light/Dark modes.

**Tech Stack:** Vue 3 Composition API, Tailwind CSS, CSS Custom Properties

---

## File Structure

| File | Purpose |
|------|---------|
| `src/composables/useThemeStore.js` | Theme state management composable |
| `src/components/layout/ThemeToggle.vue` | Toggle button component |
| `src/style.css` | Add light theme CSS variables |
| `src/App.vue` | Initialize theme on mount |
| `src/components/layout/Topbar.vue` | Add ThemeToggle to topbar |
| `tailwind.config.js` | Add `darkMode: 'class'` |

---

### Task 1: Create Theme Store Composable

**Covers:** [S4]

**Files:**
- Create: `src/composables/useThemeStore.js`

- [ ] **Step 1: Create the composable file**

```javascript
import { ref, computed, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'theme-preference'
const VALID_THEMES = ['system', 'light', 'dark']

const theme = ref('system')
const appliedTheme = ref('dark')

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
```

- [ ] **Step 2: Verify file is created**

Run: `ls src/composables/useThemeStore.js`
Expected: File exists

---

### Task 2: Create ThemeToggle Component

**Covers:** [S3]

**Files:**
- Create: `src/components/layout/ThemeToggle.vue`

- [ ] **Step 1: Create the ThemeToggle component**

```vue
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

.theme-toggle:hover {
  background: rgba(99, 102, 241, 0.1);
  color: var(--on-surface);
}
</style>
```

- [ ] **Step 2: Verify component compiles**

Run: `cd frontend && npm run build 2>&1 | head -20`
Expected: Build succeeds or only unrelated warnings

---

### Task 3: Add Light Theme CSS Variables

**Covers:** [S2, S5]

**Files:**
- Modify: `src/style.css`

- [ ] **Step 1: Add light theme variables to style.css**

Add the following after the existing `:root` block (after line 64):

```css
[data-theme="light"] {
  color-scheme: light;

  /* Surface hierarchy */
  --surface: #fefefe;
  --surface-dim: #f1f1f1;
  --surface-container-lowest: #ffffff;
  --surface-container-low: #f7f7f9;
  --surface-container: #f1f1f4;
  --surface-container-high: #e5e5ea;
  --surface-container-highest: #d9d9e0;
  --surface-bright: #ffffff;

  /* Primary */
  --primary: #3b44a8;
  --primary-container: #6366f1;
  --on-primary: #ffffff;
  --on-primary-container: #ffffff;

  /* Secondary */
  --secondary: #555e71;
  --secondary-container: #d9e3f8;
  --on-secondary: #ffffff;
  --on-secondary-container: #111c2b;

  /* Tertiary */
  --tertiary: #7c5800;
  --tertiary-container: #ffde9e;
  --on-tertiary: #ffffff;

  /* Text */
  --on-surface: #1b1b1f;
  --on-surface-variant: #44474f;

  /* Accents */
  --outline: #74777f;
  --outline-variant: #c4c6cf;
}
```

- [ ] **Step 2: Add transition rule**

Add this after the `[data-theme="light"]` block:

```css
[data-theme] * {
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
```

- [ ] **Step 3: Verify CSS is valid**

Run: `cd frontend && npx tailwindcss --input src/style.css --output /dev/null 2>&1 | head -5`
Expected: No CSS syntax errors

---

### Task 4: Initialize Theme in App.vue

**Covers:** [S4]

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: Add theme initialization to App.vue**

Add import and initialization in `<script setup>`:

```javascript
import { onMounted, onBeforeUnmount } from 'vue'
import { useThemeStore } from './composables/useThemeStore'

const { initTheme, startListening, stopListening, handleStorageEvent } = useThemeStore()
```

Add to `onMounted`:

```javascript
onMounted(() => {
  initTheme()
  startListening()
  window.addEventListener('storage', handleStorageEvent)
  // ... existing code
})
```

Add to `onBeforeUnmount`:

```javascript
onBeforeUnmount(() => {
  stopListening()
  window.removeEventListener('storage', handleStorageEvent)
  // ... existing code
})
```

- [ ] **Step 2: Verify app initializes**

Run: `cd frontend && npm run dev & sleep 3 && curl -s http://localhost:5173 | grep "data-theme" ; kill %1`
Expected: `data-theme="dark"` or `data-theme="light"` present in HTML

---

### Task 5: Add ThemeToggle to Topbar

**Covers:** [S3]

**Files:**
- Modify: `src/components/layout/Topbar.vue`

- [ ] **Step 1: Import ThemeToggle in Topbar**

Add import in `<script setup>`:

```javascript
import ThemeToggle from './ThemeToggle.vue'
```

- [ ] **Step 2: Add ThemeToggle to template**

Add before the notification button (around line 56):

```vue
<ThemeToggle />
```

- [ ] **Step 3: Verify Topbar renders**

Run: `cd frontend && npm run dev & sleep 3 && curl -s http://localhost:5173 | grep -o "theme-toggle" | head -1 ; kill %1`
Expected: `theme-toggle` class found in output

---

### Task 6: Update Tailwind Config

**Covers:** [S5]

**Files:**
- Modify: `tailwind.config.js`

- [ ] **Step 1: Add darkMode config**

Add `darkMode: 'class'` to the config:

```javascript
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    // ... existing theme config
  },
  plugins: [],
}
```

- [ ] **Step 2: Verify Tailwind processes**

Run: `cd frontend && npx tailwindcss --input src/style.css --output /dev/null 2>&1 | head -5`
Expected: No errors

---

### Task 7: Update Tailwind Theme Colors

**Covers:** [S2]

**Files:**
- Modify: `tailwind.config.js`

- [ ] **Step 1: Add light theme colors to Tailwind**

Update the `colors` section to include light theme overrides using CSS variables:

```javascript
colors: {
  surface: {
    DEFAULT: 'var(--surface)',
    dim: 'var(--surface-dim)',
    lowest: 'var(--surface-container-lowest)',
    low: 'var(--surface-container-low)',
    container: 'var(--surface-container)',
    high: 'var(--surface-container-high)',
    highest: 'var(--surface-container-highest)',
    bright: 'var(--surface-bright)',
  },
  primary: {
    DEFAULT: 'var(--primary)',
    container: 'var(--primary-container)',
    on: 'var(--on-primary)',
  },
  secondary: {
    DEFAULT: 'var(--secondary)',
    container: 'var(--secondary-container)',
    on: 'var(--on-secondary)',
  },
  tertiary: {
    DEFAULT: 'var(--tertiary)',
    container: 'var(--tertiary-container)',
  },
  on: {
    surface: 'var(--on-surface)',
    'surface-variant': 'var(--on-surface-variant)',
  },
  outline: {
    DEFAULT: 'var(--outline)',
    variant: 'var(--outline-variant)',
  },
}
```

- [ ] **Step 2: Verify Tailwind build**

Run: `cd frontend && npx tailwindcss --input src/style.css --output /dev/null 2>&1 | head -5`
Expected: No errors

---

### Task 8: Verify Theme Toggle Works

**Covers:** [S7]

**Files:**
- None (verification only)

- [ ] **Step 1: Run dev server and test manually**

Run: `cd frontend && npm run dev`

Manual verification steps:
1. Open browser to http://localhost:5173
2. Click theme toggle button in topbar
3. Verify theme changes from dark to light
4. Click again to verify it goes to system mode
5. Click again to verify it returns to dark
6. Refresh page - verify theme persists
7. Open new tab - verify theme syncs

- [ ] **Step 2: Check contrast ratios**

Verify text is readable in both themes:
- Primary text (`--on-surface`) on background (`--surface`)
- Secondary text (`--on-surface-variant`) on background
- Button text on button backgrounds

Expected: All combinations meet WCAG AA (4.5:1 for normal text, 3:1 for large text)

---

### Task 9: Commit Changes

**Covers:** All sections

**Files:**
- All modified files

- [ ] **Step 1: Stage all changes**

```bash
git add src/composables/useThemeStore.js \
        src/components/layout/ThemeToggle.vue \
        src/style.css \
        src/App.vue \
        src/components/layout/Topbar.vue \
        tailwind.config.js
```

- [ ] **Step 2: Commit with descriptive message**

```bash
git commit -m "feat: add light/dark mode toggle with system preference support

- Add useThemeStore composable for theme state management
- Add ThemeToggle component with System/Light/Dark cycle
- Add Material Design 3 light theme CSS variables
- Initialize theme on app mount with localStorage persistence
- Support cross-tab sync via storage events
- Add Tailwind darkMode class strategy"
```

- [ ] **Step 3: Verify commit**

Run: `git log -1 --oneline`
Expected: Commit message visible
