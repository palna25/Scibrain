import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ResearchProvider } from "./context/ResearchContext.jsx";


createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ResearchProvider>
      <App />
    </ResearchProvider>
  </StrictMode>,
)
