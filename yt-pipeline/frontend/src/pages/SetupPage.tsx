import { useEffect, useState } from 'react'
import { api, type AppSettings } from '../api'

const defaultSettings = (): AppSettings => ({
  setup_complete: false,
  workspace_dir: '',
  llm: {
    provider: 'mock',
    base_url: 'https://api.openai.com/v1',
    api_key_env: 'LLM_API_KEY',
    api_key: '',
    model: 'gpt-4.1-mini',
    temperature: 0.7,
  },
  tts: {
    provider: 'mock',
    api_key_env: 'TTS_API_KEY',
    api_key: '',
    voice: 'alloy',
    model: 'gpt-4o-mini-tts',
    speaking_rate: 1,
    words_per_minute: 150,
  },
  video: {
    width: 1920,
    height: 1080,
    fps: 30,
    video_bitrate: '6M',
    audio_bitrate: '192k',
    gameplay_library_dir: '',
    default_bed_mode: 'shuffle_clips',
    crossfade_frames: 0,
  },
  thumbnail: {
    mode: 'template',
    template_id: 'bold_title',
    font_path: '',
    default_text_color: '#FFFFFF',
    default_accent_color: '#FF3B30',
  },
  youtube_defaults: {
    description_footer: '',
    default_tags: ['gaming', 'analysis'],
    visibility: 'private',
    stop_for_review: true,
  },
})

export default function SetupPage() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings())
  const [health, setHealth] = useState<string>('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch((e) => setErr(String(e.message || e)))
    api
      .health()
      .then((h) =>
        setHealth(
          `FFmpeg: ${h.ffmpeg ? 'ok' : 'missing'} · workspace: ${h.workspace_configured ? 'set' : 'no'} · setup: ${h.setup_complete ? 'done' : 'incomplete'}`,
        ),
      )
      .catch(() => setHealth('API offline'))
  }, [])

  async function save(markComplete = false) {
    setSaving(true)
    setErr('')
    setMsg('')
    try {
      const next = { ...settings, setup_complete: markComplete || settings.setup_complete }
      if (markComplete) next.setup_complete = true
      const saved = await api.putSettings(next)
      setSettings(saved)
      setMsg(markComplete ? 'Setup saved and marked complete.' : 'Settings saved.')
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  async function test(kind: 'llm' | 'tts') {
    setErr('')
    setMsg('')
    try {
      await save(false)
      const res = kind === 'llm' ? await api.testLlm() : await api.testTts()
      setMsg(res.message)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <h1>Setup</h1>
      <p className="sub">Local workspace, providers, and defaults. Keys stay on this machine.</p>
      {health && <p className="muted">{health}</p>}

      <div className="panel">
        <h2>1. Workspace</h2>
        <label>
          Workspace directory
          <input
            value={settings.workspace_dir}
            onChange={(e) => setSettings({ ...settings, workspace_dir: e.target.value })}
            placeholder="/path/to/yt-workspace"
          />
        </label>
        <label>
          Gameplay library directory
          <input
            value={settings.video.gameplay_library_dir}
            onChange={(e) =>
              setSettings({
                ...settings,
                video: { ...settings.video, gameplay_library_dir: e.target.value },
              })
            }
            placeholder="Optional — defaults to workspace/gameplay"
          />
        </label>
      </div>

      <div className="panel">
        <h2>2. Script LLM</h2>
        <div className="grid-2">
          <label>
            Provider
            <select
              value={settings.llm.provider}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  llm: { ...settings.llm, provider: e.target.value as AppSettings['llm']['provider'] },
                })
              }
            >
              <option value="mock">mock (offline)</option>
              <option value="openai_compatible">openai_compatible</option>
            </select>
          </label>
          <label>
            Model
            <input
              value={settings.llm.model}
              onChange={(e) => setSettings({ ...settings, llm: { ...settings.llm, model: e.target.value } })}
            />
          </label>
        </div>
        <label>
          Base URL
          <input
            value={settings.llm.base_url}
            onChange={(e) => setSettings({ ...settings, llm: { ...settings.llm, base_url: e.target.value } })}
          />
        </label>
        <label>
          API key (or set LLM_API_KEY in env)
          <input
            type="password"
            value={settings.llm.api_key}
            onChange={(e) => setSettings({ ...settings, llm: { ...settings.llm, api_key: e.target.value } })}
            placeholder={settings.llm.api_key_set ? 'Key saved' : 'sk-...'}
          />
        </label>
        <div className="row">
          <button className="btn" type="button" onClick={() => test('llm')}>
            Test LLM
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>3. TTS</h2>
        <div className="grid-2">
          <label>
            Provider
            <select
              value={settings.tts.provider}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  tts: { ...settings.tts, provider: e.target.value as AppSettings['tts']['provider'] },
                })
              }
            >
              <option value="mock">mock (tone wav)</option>
              <option value="openai">openai</option>
            </select>
          </label>
          <label>
            Voice
            <input
              value={settings.tts.voice}
              onChange={(e) => setSettings({ ...settings, tts: { ...settings.tts, voice: e.target.value } })}
            />
          </label>
        </div>
        <label>
          API key (or set TTS_API_KEY in env)
          <input
            type="password"
            value={settings.tts.api_key}
            onChange={(e) => setSettings({ ...settings, tts: { ...settings.tts, api_key: e.target.value } })}
            placeholder={settings.tts.api_key_set ? 'Key saved' : 'sk-...'}
          />
        </label>
        <div className="row">
          <button className="btn" type="button" onClick={() => test('tts')}>
            Test TTS
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>4. Defaults</h2>
        <div className="grid-2">
          <label>
            Output width
            <input
              type="number"
              value={settings.video.width}
              onChange={(e) =>
                setSettings({ ...settings, video: { ...settings.video, width: Number(e.target.value) } })
              }
            />
          </label>
          <label>
            Output height
            <input
              type="number"
              value={settings.video.height}
              onChange={(e) =>
                setSettings({ ...settings, video: { ...settings.video, height: Number(e.target.value) } })
              }
            />
          </label>
        </div>
        <label>
          Description footer
          <textarea
            value={settings.youtube_defaults.description_footer}
            onChange={(e) =>
              setSettings({
                ...settings,
                youtube_defaults: { ...settings.youtube_defaults, description_footer: e.target.value },
              })
            }
          />
        </label>
        <label>
          <span className="row">
            <input
              type="checkbox"
              checked={settings.youtube_defaults.stop_for_review}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  youtube_defaults: { ...settings.youtube_defaults, stop_for_review: e.target.checked },
                })
              }
            />
            Stop at needs_review after full runs
          </span>
        </label>
      </div>

      <div className="row">
        <button className="btn" disabled={saving} onClick={() => save(false)}>
          Save
        </button>
        <button className="btn primary" disabled={saving || !settings.workspace_dir} onClick={() => save(true)}>
          Save & finish setup
        </button>
      </div>
      {msg && <p className="ok-msg">{msg}</p>}
      {err && <p className="error">{err}</p>}
    </div>
  )
}
