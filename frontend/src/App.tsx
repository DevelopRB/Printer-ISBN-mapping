import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { PrinterHealthProvider } from './lib/printerHealth'
import { AutomatedReconciliationPage } from './pages/AutomatedReconciliationPage'
import { DashboardPage } from './pages/DashboardPage'
import { HowToPage } from './pages/HowToPage'
import { PrinterConfigPage } from './pages/PrinterConfigPage'

export default function App() {
  return (
    <BrowserRouter>
      <PrinterHealthProvider>
        <Routes>
          {/* Default landing: Automated Reconciliation */}
          <Route path="/" element={<Navigate to="/automated" replace />} />
          <Route path="/automated" element={<AutomatedReconciliationPage />} />
          {/* Emergency / fallback workflow — still fully available */}
          <Route path="/manual" element={<DashboardPage />} />
          <Route path="/printers" element={<PrinterConfigPage />} />
          <Route path="/how-to" element={<HowToPage />} />
          <Route path="*" element={<Navigate to="/automated" replace />} />
        </Routes>
      </PrinterHealthProvider>
    </BrowserRouter>
  )
}
