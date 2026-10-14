import React from 'react'
import ReactDOM from 'react-dom/client'
// Ordem: fontes e variáveis do sistema visual, depois o Tailwind, depois a casca
// e os componentes base. O App.css (telas antigas) entra pelo App.tsx, por cima.
import './theme/fontes.css'
import './theme/tokens.css'
import './index.css'
import './theme/componentes.css'
import App from './App'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element #root not found')
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
