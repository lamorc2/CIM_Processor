import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Job } from '../api'

function statusChip(status: string) {
  const cls =
    status === 'succeeded' || status === 'needs_review'
      ? 'ok'
      : status === 'failed'
        ? 'bad'
        : status === 'running' || status === 'queued'
          ? 'run'
          : status === 'cancelled'
            ? 'warn'
            : ''
  return <span className={`chip ${cls}`}>{status}</span>
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [err, setErr] = useState('')
  const [ready, setReady] = useState(false)
  const nav = useNavigate()

  async function refresh() {
    try {
      const h = await api.health()
      setReady(h.workspace_configured)
      if (!h.workspace_configured) {
        setJobs([])
        return
      }
      setJobs(await api.listJobs())
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function create() {
    setErr('')
    try {
      const job = await api.createJob({ title, prompt_user: prompt })
      nav(`/jobs/${job.id}`)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <h1>Jobs</h1>
      <p className="sub">Create a video job — title, prompts, clips, thumbnail — then run the pipeline.</p>

      {!ready && (
        <div className="panel">
          <p>
            Workspace not configured. <Link to="/setup">Complete Setup</Link> first.
          </p>
        </div>
      )}

      <div className="panel">
        <h2>New job</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Video title" />
        </label>
        <label>
          Prompt / topic notes
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Topic, angle, tone, must-include bullets..."
          />
        </label>
        <button className="btn primary" disabled={!ready || !title.trim()} onClick={create}>
          Create job
        </button>
      </div>

      <div className="panel">
        <h2>Recent</h2>
        {jobs.length === 0 ? (
          <p className="muted">No jobs yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>
                    <Link to={`/jobs/${j.id}`}>{j.inputs.title || j.id}</Link>
                  </td>
                  <td>{statusChip(j.status)}</td>
                  <td className="muted">{new Date(j.updated_at).toLocaleString()}</td>
                  <td>
                    <Link className="btn" to={`/jobs/${j.id}`}>
                      Open
                    </Link>
                  </td>
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
