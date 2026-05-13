import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import { Layout } from './components/layout/Layout'
import { Overview } from './pages/Overview'
import { Signals } from './pages/Signals'
import { Trades } from './pages/Trades'
import { Positions } from './pages/Positions'
import { Sources } from './pages/Sources'
import { RiskControls } from './pages/RiskControls'
import { Settings } from './pages/Settings'
import { Backtest } from './pages/Backtest'
import { Reports } from './pages/Reports'
import { Logs } from './pages/Logs'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="signals" element={<Signals />} />
          <Route path="trades" element={<Trades />} />
          <Route path="positions" element={<Positions />} />
          <Route path="sources" element={<Sources />} />
          <Route path="risk" element={<RiskControls />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="reports" element={<Reports />} />
          <Route path="logs" element={<Logs />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
