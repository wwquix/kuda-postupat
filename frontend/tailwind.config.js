/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--color-background) / <alpha-value>)',
        elevated: 'rgb(var(--color-elevated) / <alpha-value>)',
        'text-primary': 'rgb(var(--color-text-primary) / <alpha-value>)',
        'text-secondary': 'rgb(var(--color-text-secondary) / <alpha-value>)',
        accent: 'rgb(var(--color-accent) / <alpha-value>)',
        'accent-soft': 'rgb(var(--color-accent-soft) / <alpha-value>)',
        border: 'rgb(var(--color-border) / <alpha-value>)',
        focus: 'rgb(var(--color-focus) / <alpha-value>)',
        success: 'rgb(var(--color-success) / <alpha-value>)',
        warning: 'rgb(var(--color-warning) / <alpha-value>)',
        danger: 'rgb(var(--color-danger) / <alpha-value>)',
        'glass-compact': 'rgb(var(--color-glass-compact) / <alpha-value>)',
        'glass-strong': 'rgb(var(--color-glass-strong) / <alpha-value>)',
        ink: 'rgb(var(--color-text-primary) / <alpha-value>)',
        moss: 'rgb(var(--color-accent) / <alpha-value>)',
        mint: 'rgb(var(--color-accent-soft) / <alpha-value>)',
        cream: 'rgb(var(--color-background) / <alpha-value>)',
        amber: 'rgb(var(--color-warning) / <alpha-value>)',
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
        card: 'var(--shadow-elevated)',
        'glass-compact': 'var(--shadow-glass-compact)',
        'glass-strong': 'var(--shadow-glass-strong)',
      },
    },
  },
  plugins: [],
}
