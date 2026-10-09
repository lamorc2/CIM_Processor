import { useEffect, useState } from 'react'
import { api } from '../api'

export default function LibraryPage() {
  const [clips, setClips] = useState<Array<{ path: string; name: string; size_bytes: number }>>([])
  const [err, setErr] = useState('')

  useEffect(() => {
    api
      .libraryClips()
      .then(setClips)
      .catch((e) => setErr(String(e.message || e)))
  }, [])

  return (
    <div>
      <h1>Library</h1>
      <p className="sub">Gameplay clips discovered in your library folder from Setup.</p>
      <div className="panel">
        {clips.length === 0 ? (
          <p className="muted">No clips found. Add .mp4/.mov files to the gameplay library directory.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {clips.map((c) => (
                <tr key={c.path}>
                  <td>{c.name}</td>
                  <td className="muted">{(c.size_bytes / 1024 / 1024).toFixed(1)} MB</td>
                  <td className="muted">{c.path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {err && <p className="error">{err}</p>}
    </div>
  )
}
