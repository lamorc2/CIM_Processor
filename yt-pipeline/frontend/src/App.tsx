import { NavLink, Route, Routes } from 'react-router-dom'
import SetupPage from './pages/SetupPage'
import JobsPage from './pages/JobsPage'
import JobPage from './pages/JobPage'
import LibraryPage from './pages/LibraryPage'

export default function App() {
  return (
    <div className="app-shell">
      <nav className="nav">
        <div className="brand">
          Pipe<span>cast</span>
        </div>
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
          Jobs
        </NavLink>
        <NavLink to="/setup" className={({ isActive }) => (isActive ? 'active' : undefined)}>
          Setup
        </NavLink>
        <NavLink to="/library" className={({ isActive }) => (isActive ? 'active' : undefined)}>
          Library
        </NavLink>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/jobs/:id" element={<JobPage />} />
        </Routes>
      </main>
    </div>
  )
}
