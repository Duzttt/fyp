/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#7C3AED',
        secondary: '#A78BFA',
        cta: '#06B6D4',
        background: '#FAF5FF',
        text: '#1E1B4B',
      },
      fontFamily: {
        'heading': ['Baloo 2', 'cursive'],
        'body': ['Comic Neue', 'sans-serif'],
      },
      boxShadow: {
        'card': '0 4px 6px rgba(0,0,0,0.1)',
        'card-hover': '0 10px 15px rgba(0,0,0,0.1)',
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-subtle': 'bounce 1s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
