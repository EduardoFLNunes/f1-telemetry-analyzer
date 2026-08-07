/** @type {import('tailwindcss').Config} */
// Mirrors the config that used to live inline in index.html against the Tailwind
// CDN. Building locally means the packaged desktop app keeps its layout with no
// network access, which the CDN could not guarantee.
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', '"Cascadia Mono"', 'monospace'],
        sans: ['Inter', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
