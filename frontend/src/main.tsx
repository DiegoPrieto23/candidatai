import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import './index.css'
import { App } from './App.tsx'
import { createQueryClient } from './lib/queryClient'
import { i18nReady } from './lib/i18n'
import { applyTheme } from './lib/theme'

applyTheme() // antes de pintar: sin destello del tema equivocado

// Con los textos del idioma ya cargados: ningún texto se pinta antes en blanco o con su clave. Si
// no llegan (el servidor se ha parado), se pinta igual en vez de dejar la página en blanco.
void i18nReady.catch(() => undefined).then(() =>
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <BrowserRouter>
        <App client={createQueryClient()} />
      </BrowserRouter>
    </StrictMode>,
  ),
)
