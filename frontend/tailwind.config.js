/** @type {import('tailwindcss').Config} */
// Tailwind compilado no bundle (sem CDN), para o app instalado funcionar sem
// internet. As cores e as fontes apontam para as variáveis de
// src/theme/tokens.css (pedido 29): um lugar só para cada cor.
const v = (nome) => `var(--${nome})`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        fundo: v('fundo'),
        superficie: { DEFAULT: v('superficie'), 2: v('superficie-2'), 3: v('superficie-3') },
        linha: { DEFAULT: v('linha'), fraca: v('linha-fraca') },
        texto: { 1: v('texto-1'), 2: v('texto-2'), 3: v('texto-3') },
        vermelho: { DEFAULT: v('vermelho'), claro: v('vermelho-claro'), escuro: v('vermelho-escuro') },
        freio: v('freio'),
        acelerador: v('acelerador'),
        parcial: v('parcial'),
        perda: v('perda'),
        ganho: v('ganho'),
        voce: v('voce'),
        referencia: v('referencia'),
        tempo: { roxo: v('tempo-roxo'), verde: v('tempo-verde'), amarelo: v('tempo-amarelo') },
        estado: { ok: v('estado-ok'), aviso: v('estado-aviso'), erro: v('estado-erro'), neutro: v('estado-neutro') },
      },
      fontFamily: {
        titulo: ['"Barlow Condensed"', '"Arial Narrow"', 'sans-serif'],
        sans: ['"Instrument Sans"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'Consolas', '"Cascadia Mono"', 'monospace'],
      },
      borderRadius: {
        vidro: v('raio-3'),
      },
    },
  },
  plugins: [],
};
