/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#dde8ff',
          200: '#c4d5ff',
          300: '#9ab8ff',
          400: '#6d91ff',
          500: '#4a6cf7',
          600: '#3451eb',
          700: '#2a3fd8',
          800: '#2635af',
          900: '#253089',
          950: '#161c54',
        },
      },
    },
  },
  plugins: [],
}
