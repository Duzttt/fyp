# Light & Dark Mode Design Spec

**Date:** 2026-06-15
**Status:** Approved

## [S1] Problem Statement

The current UI is dark-mode only. Users need the ability to switch between light and dark themes, with an option to follow the OS system preference. This improves accessibility and user comfort in different lighting conditions.

## [S2] Color System Architecture

**Approach:** Material Design 3 Light palette, mirroring the existing dark theme structure.

**Light Mode Colors** (to be added to `:root` under `[data-theme="light"]`):

| Token | Light Value | Dark Value (existing) |
|-------|-------------|----------------------|
| `--surface` | `#fefefe` | `#0b1326` |
| `--surface-dim` | `#f1f1f1` | `#0b1326` |
| `--surface-container-lowest` | `#ffffff` | `#060e20` |
| `--surface-container-low` | `#f7f7f9` | `#131b2e` |
| `--surface-container` | `#f1f1f4` | `#171f33` |
| `--surface-container-high` | `#e5e5ea` | `#222a3d` |
| `--surface-container-highest` | `#d9d9e0` | `#2d3449` |
| `--surface-bright` | `#ffffff` | `#31394d` |
| `--primary` | `#3b44a8` | `#bdc2ff` |
| `--primary-container` | `#6366f1` | `#818cf8` |
| `--on-primary` | `#ffffff` | `#131e8c` |
| `--on-primary-container` | `#ffffff` | `#101b8a` |
| `--secondary` | `#555e71` | `#bcc7de` |
| `--secondary-container` | `#d9e3f8` | `#3e495d` |
| `--on-secondary` | `#ffffff` | `#263143` |
| `--on-secondary-container` | `#111c2b` | `#aeb9d0` |
| `--tertiary` | `#7c5800` | `#f7bd3e` |
| `--tertiary-container` | `#ffde9e` | `#c08d00` |
| `--on-tertiary` | `#ffffff` | `#402d00` |
| `--on-surface` | `#1b1b1f` | `#dae2fd` |
| `--on-surface-variant` | `#44474f` | `#c6c5d5` |
| `--outline` | `#74777f` | `#908f9e` |
| `--outline-variant` | `#c4c6cf` | `#454653` |

**Implementation:** Use `[data-theme="light"]` and `[data-theme="dark"]` selectors on `<html>`. The dark colors become the default fallback (existing behavior).

## [S3] Theme Toggle Component

**Location:** Topbar, before the avatar (right side).

**Behavior:**
- Three-state cycle: System → Light → Dark → System
- Icons: `Monitor` (System), `Sun` (Light), `Moon` (Dark)
- Tooltip shows current mode on hover
- 200ms smooth transition when switching

**Visual Design:**
- 34x34px circular button matching existing `icon-btn` style
- Active state: slight background tint (`rgba(99, 102, 241, 0.1)`)
- Icon color matches `--on-surface-variant`

**Component Structure:**
```
ThemeToggle.vue
├── State: currentTheme ('system' | 'light' | 'dark')
├── Method: cycleTheme() - rotates through modes
├── Method: applyTheme() - sets data-theme attribute
├── Lifecycle: onMounted - read from localStorage or detect OS preference
└── Watch: localStorage changes (cross-tab sync)
```

## [S4] Theme Store (Composable)

**Approach:** Use a Vue composable (`useThemeStore.js`) rather than Pinia, since theme is a simple UI state, not business logic.

**State:**
- `theme`: `'system' | 'light' | 'dark'` - current preference
- `appliedTheme`: `'light' | 'dark'` - resolved theme (after OS detection)

**Methods:**
- `setTheme(mode)` - saves to localStorage, applies to DOM
- `cycleTheme()` - rotates: system → light → dark → system
- `initTheme()` - reads from localStorage on app mount, falls back to OS preference

**OS Detection:**
```js
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)')
```

**localStorage Key:** `theme-preference`

**Cross-tab Sync:** Listen for `storage` event on `window` to sync theme changes across tabs.

## [S5] CSS Implementation

**Strategy:** Extend existing `:root` variables with light theme overrides.

```css
/* style.css additions */
:root {
  color-scheme: dark;
  /* ... existing dark variables ... */
}

[data-theme="light"] {
  color-scheme: light;
  /* ... light mode variables ... */
}

/* Smooth transition */
* {
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
```

**Tailwind Integration:** Add `darkMode: 'class'` to `tailwind.config.js` to enable Tailwind's dark mode utilities (for any hardcoded classes).

## [S6] Files to Modify

| File | Change |
|------|--------|
| `src/style.css` | Add `[data-theme="light"]` CSS variables, add transition rule |
| `src/composables/useThemeStore.js` | New file - theme state management |
| `src/components/layout/Topbar.vue` | Add ThemeToggle button, import composable |
| `src/components/layout/ThemeToggle.vue` | New file - toggle button component |
| `src/App.vue` | Initialize theme on mount |
| `tailwind.config.js` | Add `darkMode: 'class'` |

**Total new files:** 2
**Total modified files:** 4

## [S7] Testing Strategy

1. **Visual:** Verify all components render correctly in both themes
2. **Persistence:** Theme choice survives page reload
3. **OS Preference:** "System" mode correctly follows OS setting
4. **Cross-tab:** Theme changes sync across browser tabs
5. **Transition:** Smooth 200ms fade on theme switch
6. **Accessibility:** Focus states, contrast ratios meet WCAG AA
