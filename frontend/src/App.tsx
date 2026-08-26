import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AutomatedReconciliationPage } from './pages/AutomatedReconciliationPage'
import { DashboardPage } from './pages/DashboardPage'
import { PrinterConfigPage } from './pages/PrinterConfigPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/automated" element={<AutomatedReconciliationPage />} />
        <Route path="/printers" element={<PrinterConfigPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
