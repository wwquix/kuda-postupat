/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#13291f',
        moss: '#19664a',
        mint: '#dff4e9',
        cream: '#f6f4ed',
        amber: '#d99b35',
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 18px 50px rgba(19, 41, 31, 0.08)' },
    },
  },
  plugins: [],
}
