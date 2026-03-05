/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-main': '#111827',
        'bg-panel': '#111827',
        'bg-panel-soft': '#020617',
        'bg-chip': '#1f2937',
        'border-subtle': '#1f2937',
        'border-strong': '#374151',
        'text-main': '#e5e7eb',
        'text-muted': '#9ca3af',
        'accent': '#6366f1',
        'accent-soft': '#312e81',
      },
    },
  },
  plugins: [],
}
