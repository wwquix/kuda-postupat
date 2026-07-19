/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--color-background) / <alpha-value>)',
        elevated: 'rgb(var(--color-elevated) / <alpha-value>)',
        'text-primary': 'rgb(var(--color-text-primary-rgb) / <alpha-value>)',
        'text-secondary': 'rgb(var(--color-text-secondary-rgb) / <alpha-value>)',
        'text-tertiary': 'rgb(var(--color-text-tertiary-rgb) / <alpha-value>)',
        accent: 'rgb(var(--color-accent-rgb) / <alpha-value>)',
        'accent-soft': 'rgb(var(--color-accent-soft) / <alpha-value>)',
        border: 'rgb(var(--color-border-rgb) / <alpha-value>)',
        divider: 'rgb(var(--color-divider-rgb) / <alpha-value>)',
        focus: 'rgb(var(--color-focus-rgb) / <alpha-value>)',
        success: 'rgb(var(--color-success-rgb) / <alpha-value>)',
        warning: 'rgb(var(--color-warning-rgb) / <alpha-value>)',
        danger: 'rgb(var(--color-danger-rgb) / <alpha-value>)',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Display',
          'Segoe UI',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: 'var(--shadow-solid)',
        'glass-compact': 'var(--shadow-compact)',
        'glass-strong': 'var(--shadow-strong)',
      },
    },
  },
  plugins: [],
}
