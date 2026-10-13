import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import './index.css'
import { App } from './App.tsx'
import { createQueryClient } from './lib/queryClient'
import './lib/i18n'
import { applyTheme } from './lib/theme'

applyTheme() // antes de pintar: sin destello del tema equivocado

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App client={createQueryClient()} />
    </BrowserRouter>
  </StrictMode>,
)
