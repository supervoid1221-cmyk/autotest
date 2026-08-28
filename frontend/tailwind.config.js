module.exports = {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  important: true,
  theme: {
    extend: {
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#F3F4FF',
          100: '#DFE3FF',
          200: '#C4C9FF',
          400: '#8B92F5',
          600: '#5B6AF0',
          800: '#3E4DD0',
          900: '#2D3BA0',
        },
        success: {
          50: '#ECFDF5',
          500: '#10B981',
          600: '#059669',
        },
        danger: {
          50: '#FFF1F2',
          500: '#F43F5E',
          600: '#E11D48',
        },
      },
    },
  },
};
