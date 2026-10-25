/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Grafana dark palette
        carbon: '#0b0c0e',
        panel: '#181b1f',
        'panel-hover': '#1f2228',
        edge: '#22252b',
        'edge-strong': '#2c3038',
        ink: '#d8d9da',
        'ink-dim': '#9aa0a6',
        'ink-faint': '#6e7378',
        emerald: { DEFAULT: '#73bf69', dim: '#2f6b3a' },
        cyan: { DEFAULT: '#5ef2ff', dim: '#1f6f7a' },
        amber: '#fade2a',
        orange: '#ff9830',
        red: '#f2495c',
        blue: '#5794f2',
        purple: '#b877d9',
        pink: '#f26bb3',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.02) inset',
      },
    },
  },
  plugins: [],
};
