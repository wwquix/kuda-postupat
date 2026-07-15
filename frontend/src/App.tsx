import { Route, Routes } from 'react-router-dom'

import { SiteLayout } from './components/SiteLayout'
import { HomePage } from './pages/HomePage'
import MonitorPage from './pages/MonitorPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { UniversityDetailPage } from './pages/UniversityDetailPage'
import { UniversitiesPage } from './pages/UniversitiesPage'

export default function App() {
  return <Routes>
    <Route element={<SiteLayout />}>
      <Route index element={<HomePage />} />
      <Route path="universities" element={<UniversitiesPage />} />
      <Route path="universities/:slug" element={<UniversityDetailPage />} />
      <Route path="monitor" element={<MonitorPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Route>
  </Routes>
}
