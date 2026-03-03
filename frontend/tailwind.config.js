/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#f97316',      // warm orange accent
        secondary: '#fb923c',
        cta: '#22C55E',
        background: '#020617',   // near-black background
        surface: '#0B1120',      // slightly lighter surface
        text: '#E5E7EB',
        muted: '#9CA3AF',
      },
      fontFamily: {
        heading: ['Poppins', 'sans-serif'],
        body: ['Open Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
