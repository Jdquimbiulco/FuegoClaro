/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#05080E',
          900: '#070C14',
          850: '#0A111B',
          800: '#0D1622',
          750: '#101C2B',
          700: '#152336',
          600: '#1D3048',
          500: '#2A415D',
        },
        ember: {
          50: '#FFF6ED',
          100: '#FFE7CC',
          200: '#FFC894',
          300: '#FFA45C',
          400: '#FF7A2F',
          500: '#FF5C16',
          600: '#E8470B',
          700: '#B9350A',
        },
        modis: '#FFB020',
        viirs: '#FF4D5E',
        mint: '#3DDC97',
        slateish: '#8EA3BE',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 50px -30px rgba(0,0,0,0.9)',
        ember: '0 0 24px -6px rgba(255,92,22,0.55)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 320ms ease-out both',
        'pulse-soft': 'pulseSoft 2.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
