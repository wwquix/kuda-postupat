import { Route, Routes } from 'react-router-dom'

import { SiteLayout } from './components/SiteLayout'
import { ProfileProvider } from './ProfileContext'
import { HomePage } from './pages/HomePage'
import { MyListPage } from './pages/MyListPage'
import MonitorPage from './pages/MonitorPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProgramDetailPage } from './pages/ProgramDetailPage'
import { UniversityDetailPage } from './pages/UniversityDetailPage'
import { UniversitiesPage } from './pages/UniversitiesPage'

export default function App() {
  return <ProfileProvider>
    <Routes>
      <Route element={<SiteLayout />}>
        <Route index element={<HomePage />} />
        <Route path="universities" element={<UniversitiesPage />} />
        <Route path="universities/:universitySlug/programs/:programKey" element={<ProgramDetailPage />} />
        <Route path="universities/:slug" element={<UniversityDetailPage />} />
        <Route path="my-list" element={<MyListPage />} />
        <Route path="monitor" element={<MonitorPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  </ProfileProvider>
}
