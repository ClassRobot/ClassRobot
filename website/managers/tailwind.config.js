/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Light-mode palette (Operational Precision design system)
        surface: {
          DEFAULT: '#f8faf3',
          dim: '#d9dbd4',
          bright: '#f8faf3',
          container: {
            lowest: '#ffffff',
            low: '#f3f4ee',
            DEFAULT: '#edefe8',
            high: '#e7e9e2',
            highest: '#e1e3dd',
          },
        },
        'on-surface': '#191c19',
        'on-surface-variant': '#404946',
        outline: {
          DEFAULT: '#707976',
          variant: '#bfc9c5',
        },
        primary: {
          DEFAULT: '#28645a',
          container: '#b2eee1',
          fixed: '#b2eee1',
          'fixed-dim': '#96d2c5',
          dark: '#4da394',
        },
        'on-primary': '#ffffff',
        'on-primary-container': '#00201b',
        'on-primary-fixed': '#00201b',
        'on-primary-fixed-variant': '#0d5046',
        secondary: {
          DEFAULT: '#2b6099',
          container: '#d3e4ff',
          'fixed-dim': '#a2c9ff',
        },
        'on-secondary': '#ffffff',
        'on-secondary-container': '#001c38',
        tertiary: {
          DEFAULT: '#b7791f',
          container: '#ffdbd1',
          'fixed-dim': '#feb5a2',
        },
        'on-tertiary': '#ffffff',
        'on-tertiary-container': '#360f05',
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        'on-error': '#ffffff',
        'on-error-container': '#93000a',
        warning: {
          DEFAULT: '#b7791f',
          container: '#fff3cd',
        },
        code: {
          DEFAULT: '#f0f3ef',
        },
        sidebar: '240px',
        topbar: '48px',
      },
      fontFamily: {
        ui: ['Fira Sans', 'system-ui', 'sans-serif'],
        code: ['Fira Code', 'monospace'],
      },
      fontSize: {
        h1: ['24px', { lineHeight: '32px', letterSpacing: '-0.01em', fontWeight: '600' }],
        h2: ['18px', { lineHeight: '24px', letterSpacing: '0', fontWeight: '600' }],
        'body-md': ['14px', { lineHeight: '20px', fontWeight: '400' }],
        'body-sm': ['13px', { lineHeight: '18px', fontWeight: '400' }],
        'label-caps': ['11px', { lineHeight: '16px', letterSpacing: '0.05em', fontWeight: '700' }],
        'code-block': ['13px', { lineHeight: '20px', fontWeight: '400' }],
        'code-inline': ['12px', { lineHeight: '16px', fontWeight: '500' }],
      },
      spacing: {
        unit: '4px',
        xs: '4px',
        sm: '8px',
        md: '16px',
        lg: '24px',
        xl: '40px',
        'container-margin': '24px',
        'table-cell': '10px 12px',
        'drawer-min': '420px',
        'drawer-max': '640px',
        sidebar: '240px',
        topbar: '48px',
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        sm: '0.375rem',
        lg: '0.75rem',
        xl: '1rem',
        full: '9999px',
      },
      screens: {
        xs: '375px',
      },
    },
  },
  plugins: [],
}
