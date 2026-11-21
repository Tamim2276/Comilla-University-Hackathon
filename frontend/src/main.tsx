import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import type { Ports } from './application/ports'
import { PortsContext } from './application/portsContext'
import { config } from './config'
import { createApiClient } from './infrastructure/apiClient'
import { createLocalSessionStore } from './infrastructure/storage'

// Composition root of the app: the only place that builds the real adapters.
const ports: Ports = {
  api: createApiClient(config.apiUrl, config.requestTimeoutMs),
  session: createLocalSessionStore(),
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PortsContext value={ports}>
      <App />
    </PortsContext>
  </StrictMode>,
)
