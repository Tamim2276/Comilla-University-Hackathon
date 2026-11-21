// Routes (SRS 3.3): / start, /chat chat. /history and /admin come in D1-R5 and D2-R1.

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useSession } from './application/useSession'
import { ChatPage } from './presentation/pages/ChatPage'
import { StartPage } from './presentation/pages/StartPage'

function App() {
  const session = useSession()

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StartPage session={session} />} />
        <Route
          path="/chat"
          element={
            session.phone ? (
              <ChatPage session={session} phone={session.phone} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
