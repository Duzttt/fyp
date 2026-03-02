/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0891B2',
        secondary: '#22D3EE',
        cta: '#22C55E',
        background: '#ECFEFF',
        text: '#164E63',
      },
      fontFamily: {
        'sans': ['Fira Sans', 'sans-serif'],
        'mono': ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
