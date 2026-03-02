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
        background: '#F8FAFC',
        surface: '#FFFFFF',
        text: '#164E63',
        muted: '#64748B',
      },
      fontFamily: {
        'heading': ['Poppins', 'sans-serif'],
        'body': ['Open Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
