/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
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
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        lg: '12px',
        md: '8px',
      },
    },
  },
  plugins: [],
}
