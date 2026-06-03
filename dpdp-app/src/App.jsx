
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LoginPage from './LoginPage'
import UploadPage from './UploadPage'
import SelectionPage from './SelectionPage'
import { DpdpProvider } from './dpdp/useDpdpStore.jsx'
import ProcessPage from './dpdp/ProcessPage'
import PiiSelectionPage from './dpdp/PiiSelectionPage'
import DpdpResultPage from './dpdp/DpdpResultPage'
import RopaPreviewPage from './dpdp/RopaPreviewPage'
import ApkStatusPage from './ApkStatusPage'

export default function App() {
  return (
    <DpdpProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/apk/status/:jobId" element={<ApkStatusPage />} />
          <Route path="/select" element={<SelectionPage />} />
          <Route path="/dpdp/process" element={<ProcessPage />} />
          <Route path="/dpdp/pii" element={<PiiSelectionPage />} />
          <Route path="/dpdp/result" element={<DpdpResultPage />} />
          <Route path="/dpdp/ropa" element={<RopaPreviewPage />} />
        </Routes>
      </BrowserRouter>
    </DpdpProvider>
  )
}
