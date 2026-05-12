/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sentinel: {
          50: '#f0f4ff',
          100: '#dce8ff',
          500: '#3b6fd4',
          600: '#2d5bbf',
          700: '#1e4aa8',
          900: '#0f1f54',
        },
      },
    },
  },
  plugins: [],
}
