import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Job, type StageName } from '../api'

const STAGES: StageName[] = ['script', 'tts', 'video', 'thumbnail', 'package']

function chipFor(status: string) {
  const cls =
    status === 'succeeded'
      ? 'ok'
      : status === 'failed'
        ? 'bad'
        : status === 'running'
          ? 'run'
          : status === 'stale'
            ? 'warn'
            : ''
  return <span className={`chip ${cls}`}>{status}</span>
}

export default function JobPage() {
  const { id = '' } = useParams()
  const [job, setJob] = useState<Job | null>(null)
  const [tab, setTab] = useState<'basics' | 'prompts' | 'media' | 'thumbnail' | 'run'>('basics')
  const [script, setScript] = useState('')
  const [thumbUrl, setThumbUrl] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [presets, setPresets] = useState<
    Array<{ id: string; name: string; prompt_system: string; prompt_user_template: string }>
  >([])
  const [library, setLibrary] = useState<Array<{ path: string; name: string }>>([])

  async function refresh() {
    const j = await api.getJob(id)
    setJob(j)
    const s = await api.getScript(id)
    setScript(s.text)
    return j
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)))
    api.listPresets().then(setPresets).catch(() => {})
    api.libraryClips().then(setLibrary).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!job) return
    let url: string | null = null
    api
      .previewThumbnail({
        headline: job.inputs.thumbnail.headline || job.inputs.title,
        subheadline: job.inputs.thumbnail.subheadline,
        text_color: job.inputs.thumbnail.text_color,
        accent_color: job.inputs.thumbnail.accent_color,
        source_image_path: job.inputs.thumbnail.source_image_path,
      })
      .then((u) => {
        url = u
        setThumbUrl(u)
      })
      .catch(() => {})
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [
    job?.inputs.thumbnail.headline,
    job?.inputs.thumbnail.subheadline,
    job?.inputs.thumbnail.text_color,
    job?.inputs.thumbnail.accent_color,
    job?.inputs.thumbnail.source_image_path,
    job?.inputs.title,
  ])

  const stageRow = useMemo(() => {
    if (!job) return null
    return (
      <div className="stages">
        {STAGES.map((s) => (
          <span key={s}>
            {s} {chipFor(job.stage_state[s]?.status || 'pending')}
          </span>
        ))}
      </div>
    )
  }, [job])

  async function saveInputs() {
    if (!job) return
    setBusy(true)
    setErr('')
    try {
      const updated = await api.updateJob(id, { inputs: job.inputs })
      setJob(updated)
      setMsg('Saved.')
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function saveScript() {
    setBusy(true)
    setErr('')
    try {
      const updated = await api.updateJob(id, { script_markdown: script })
      setJob(updated)
      setMsg('Script saved (downstream stages marked stale).')
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function run(from?: StageName) {
    setBusy(true)
    setErr('')
    setMsg(from ? `Starting from ${from}...` : 'Starting full pipeline...')
    try {
      await saveInputs()
      await api.runJob(id, from)
      // Poll until not running
      for (let i = 0; i < 180; i++) {
        await new Promise((r) => setTimeout(r, 1000))
        const j = await refresh()
        if (j && j.status !== 'running' && j.status !== 'queued') {
          setMsg(j.progress_message || j.status)
          break
        }
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (!job) {
    return (
      <div>
        <p className="muted">Loading…</p>
        {err && <p className="error">{err}</p>}
      </div>
    )
  }

  return (
    <div>
      <p className="muted">
        <Link to="/">← Jobs</Link>
      </p>
      <h1>{job.inputs.title || 'Untitled job'}</h1>
      <p className="sub">
        {job.id} · {chipFor(job.status)} {job.progress_message ? `· ${job.progress_message}` : ''}
      </p>
      {stageRow}

      <div className="tabs">
        {(['basics', 'prompts', 'media', 'thumbnail', 'run'] as const).map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)} type="button">
            {t}
          </button>
        ))}
      </div>

      {tab === 'basics' && (
        <div className="panel">
          <h2>Basics</h2>
          <label>
            Title
            <input
              value={job.inputs.title}
              onChange={(e) => setJob({ ...job, inputs: { ...job.inputs, title: e.target.value } })}
            />
          </label>
          <label>
            Series
            <input
              value={job.inputs.series}
              onChange={(e) => setJob({ ...job, inputs: { ...job.inputs, series: e.target.value } })}
            />
          </label>
          <label>
            Target duration (seconds)
            <input
              type="number"
              value={job.inputs.script_constraints.target_duration_sec}
              onChange={(e) =>
                setJob({
                  ...job,
                  inputs: {
                    ...job.inputs,
                    script_constraints: {
                      ...job.inputs.script_constraints,
                      target_duration_sec: Number(e.target.value),
                    },
                  },
                })
              }
            />
          </label>
          <button className="btn primary" disabled={busy} onClick={saveInputs}>
            Save
          </button>
        </div>
      )}

      {tab === 'prompts' && (
        <div className="panel">
          <h2>Prompts</h2>
          <label>
            Load preset
            <select
              defaultValue=""
              onChange={(e) => {
                const p = presets.find((x) => x.id === e.target.value)
                if (!p || !job) return
                setJob({
                  ...job,
                  inputs: {
                    ...job.inputs,
                    prompt_system: p.prompt_system,
                    prompt_user: p.prompt_user_template
                      .replace('{{topic}}', job.inputs.title)
                      .replace('{{minutes}}', String(Math.round(job.inputs.script_constraints.target_duration_sec / 60)))
                      .replace('{{bullets}}', ''),
                  },
                })
              }}
            >
              <option value="">Select…</option>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            System prompt
            <textarea
              value={job.inputs.prompt_system}
              onChange={(e) => setJob({ ...job, inputs: { ...job.inputs, prompt_system: e.target.value } })}
            />
          </label>
          <label>
            User prompt
            <textarea
              value={job.inputs.prompt_user}
              onChange={(e) => setJob({ ...job, inputs: { ...job.inputs, prompt_user: e.target.value } })}
            />
          </label>
          <div className="row">
            <label className="row">
              <input
                type="checkbox"
                checked={job.inputs.script_constraints.include_hook}
                onChange={(e) =>
                  setJob({
                    ...job,
                    inputs: {
                      ...job.inputs,
                      script_constraints: {
                        ...job.inputs.script_constraints,
                        include_hook: e.target.checked,
                      },
                    },
                  })
                }
              />
              Include hook
            </label>
            <label className="row">
              <input
                type="checkbox"
                checked={job.inputs.script_constraints.include_cta}
                onChange={(e) =>
                  setJob({
                    ...job,
                    inputs: {
                      ...job.inputs,
                      script_constraints: {
                        ...job.inputs.script_constraints,
                        include_cta: e.target.checked,
                      },
                    },
                  })
                }
              />
              Include CTA
            </label>
          </div>
          <button className="btn primary" disabled={busy} onClick={saveInputs}>
            Save prompts
          </button>
        </div>
      )}

      {tab === 'media' && (
        <div className="panel">
          <h2>Gameplay bed</h2>
          <p className="muted">Use footage you own. Upload clips or pick from the library.</p>
          <label>
            Mode
            <select
              value={job.inputs.video_bed.mode}
              onChange={(e) =>
                setJob({
                  ...job,
                  inputs: {
                    ...job.inputs,
                    video_bed: {
                      ...job.inputs.video_bed,
                      mode: e.target.value as 'single_file' | 'shuffle_clips',
                    },
                  },
                })
              }
            >
              <option value="shuffle_clips">shuffle / sequential clips</option>
              <option value="single_file">single file</option>
            </select>
          </label>
          <label>
            Upload clip
            <input
              type="file"
              accept="video/*"
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setBusy(true)
                try {
                  const res = await api.uploadClip(id, f)
                  setJob(res.job)
                  setMsg(`Uploaded ${f.name}`)
                } catch (err: unknown) {
                  setErr(err instanceof Error ? err.message : String(err))
                } finally {
                  setBusy(false)
                }
              }}
            />
          </label>
          {library.length > 0 && (
            <label>
              Add from library
              <select
                defaultValue=""
                onChange={(e) => {
                  const path = e.target.value
                  if (!path) return
                  const paths = job.inputs.video_bed.paths.includes(path)
                    ? job.inputs.video_bed.paths
                    : [...job.inputs.video_bed.paths, path]
                  setJob({
                    ...job,
                    inputs: { ...job.inputs, video_bed: { ...job.inputs.video_bed, paths } },
                  })
                }}
              >
                <option value="">Select clip…</option>
                {library.map((c) => (
                  <option key={c.path} value={c.path}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <ul>
            {job.inputs.video_bed.paths.map((p) => (
              <li key={p} className="muted">
                {p}{' '}
                <button
                  className="btn danger"
                  type="button"
                  onClick={() =>
                    setJob({
                      ...job,
                      inputs: {
                        ...job.inputs,
                        video_bed: {
                          ...job.inputs.video_bed,
                          paths: job.inputs.video_bed.paths.filter((x) => x !== p),
                        },
                      },
                    })
                  }
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <button className="btn primary" disabled={busy} onClick={saveInputs}>
            Save media
          </button>
        </div>
      )}

      {tab === 'thumbnail' && (
        <div className="panel">
          <h2>Thumbnail</h2>
          <div className="grid-2">
            <div>
              <label>
                Headline
                <input
                  value={job.inputs.thumbnail.headline}
                  onChange={(e) =>
                    setJob({
                      ...job,
                      inputs: {
                        ...job.inputs,
                        thumbnail: { ...job.inputs.thumbnail, headline: e.target.value },
                      },
                    })
                  }
                />
              </label>
              <label>
                Subheadline
                <input
                  value={job.inputs.thumbnail.subheadline}
                  onChange={(e) =>
                    setJob({
                      ...job,
                      inputs: {
                        ...job.inputs,
                        thumbnail: { ...job.inputs.thumbnail, subheadline: e.target.value },
                      },
                    })
                  }
                />
              </label>
              <div className="grid-2">
                <label>
                  Text
                  <input
                    type="color"
                    value={job.inputs.thumbnail.text_color}
                    onChange={(e) =>
                      setJob({
                        ...job,
                        inputs: {
                          ...job.inputs,
                          thumbnail: { ...job.inputs.thumbnail, text_color: e.target.value },
                        },
                      })
                    }
                  />
                </label>
                <label>
                  Accent
                  <input
                    type="color"
                    value={job.inputs.thumbnail.accent_color}
                    onChange={(e) =>
                      setJob({
                        ...job,
                        inputs: {
                          ...job.inputs,
                          thumbnail: { ...job.inputs.thumbnail, accent_color: e.target.value },
                        },
                      })
                    }
                  />
                </label>
              </div>
              <label>
                Background image
                <input
                  type="file"
                  accept="image/*"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (!f) return
                    const res = await api.uploadThumbSource(id, f)
                    setJob(res.job)
                  }}
                />
              </label>
              <button className="btn primary" disabled={busy} onClick={saveInputs}>
                Save thumbnail settings
              </button>
            </div>
            <div>{thumbUrl && <img className="thumb-preview" src={thumbUrl} alt="Thumbnail preview" />}</div>
          </div>
        </div>
      )}

      {tab === 'run' && (
        <div className="panel">
          <h2>Run & review</h2>
          <div className="row" style={{ marginBottom: '1rem' }}>
            <button className="btn primary" disabled={busy} onClick={() => run()}>
              Run full pipeline
            </button>
            {STAGES.map((s) => (
              <button key={s} className="btn" disabled={busy} onClick={() => run(s)}>
                From {s}
              </button>
            ))}
          </div>

          <label>
            Script
            <textarea value={script} onChange={(e) => setScript(e.target.value)} style={{ minHeight: 220 }} />
          </label>
          <button className="btn" disabled={busy} onClick={saveScript}>
            Save script edits
          </button>

          {job.outputs.audio_path && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Audio</h3>
              <audio className="media" controls src={`/api/jobs/${id}/files/audio`} />
            </div>
          )}
          {job.outputs.video_path && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Video</h3>
              <video className="media" controls src={`/api/jobs/${id}/files/video`} />
            </div>
          )}
          {job.outputs.thumbnail_path && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Exported thumbnail</h3>
              <img className="thumb-preview" src={`/api/jobs/${id}/files/thumbnail`} alt="Exported thumbnail" />
            </div>
          )}
          {job.outputs.package_dir && (
            <p className="ok-msg" style={{ marginTop: '1rem' }}>
              Export ready at: {job.outputs.package_dir}
            </p>
          )}
          {job.last_error && <p className="error">{job.last_error}</p>}
        </div>
      )}

      {msg && <p className="ok-msg">{msg}</p>}
      {err && <p className="error">{err}</p>}
    </div>
  )
}
