export type StageName = 'script' | 'tts' | 'video' | 'thumbnail' | 'package'

export type AppSettings = {
  setup_complete: boolean
  workspace_dir: string
  llm: {
    provider: 'openai_compatible' | 'mock'
    base_url: string
    api_key_env: string
    api_key: string
    model: string
    temperature: number
    api_key_set?: boolean
  }
  tts: {
    provider: 'openai' | 'mock'
    api_key_env: string
    api_key: string
    voice: string
    model: string
    speaking_rate: number
    words_per_minute: number
    api_key_set?: boolean
  }
  video: {
    width: number
    height: number
    fps: number
    video_bitrate: string
    audio_bitrate: string
    gameplay_library_dir: string
    default_bed_mode: 'single_file' | 'shuffle_clips'
    crossfade_frames: number
  }
  thumbnail: {
    mode: 'template' | 'upload' | 'generate'
    template_id: string
    font_path: string
    default_text_color: string
    default_accent_color: string
  }
  youtube_defaults: {
    description_footer: string
    default_tags: string[]
    visibility: string
    stop_for_review: boolean
  }
}

export type Job = {
  id: string
  status: string
  created_at: string
  updated_at: string
  inputs: {
    title: string
    series: string
    prompt_system: string
    prompt_user: string
    script_constraints: {
      target_duration_sec: number
      word_count_min: number
      word_count_max: number
      include_hook: boolean
      include_cta: boolean
      banned_phrases: string[]
    }
    thumbnail: {
      mode: 'template' | 'upload' | 'generate'
      headline: string
      subheadline: string
      source_image_path: string
      template_id: string
      style_prompt: string
      text_color: string
      accent_color: string
    }
    video_bed: {
      mode: 'single_file' | 'shuffle_clips'
      paths: string[]
      mute_source_audio: boolean
      loop_if_short: boolean
    }
    tts: {
      voice_override: string | null
      speaking_rate_override: number | null
    }
  }
  outputs: {
    script_path?: string | null
    audio_path?: string | null
    video_path?: string | null
    thumbnail_path?: string | null
    package_dir?: string | null
  }
  stage_state: Record<
    string,
    { status: string; attempts: number; error: string | null; updated_at?: string | null }
  >
  last_error?: string | null
  progress_message?: string
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  health: () => req<{ ok: boolean; ffmpeg: boolean; setup_complete: boolean; workspace_configured: boolean }>('/api/health'),
  getSettings: () => req<AppSettings>('/api/settings'),
  putSettings: (body: AppSettings) =>
    req<AppSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(body) }),
  testLlm: () => req<{ ok: boolean; message: string }>('/api/settings/test-llm', { method: 'POST', body: '{}' }),
  testTts: () => req<{ ok: boolean; message: string }>('/api/settings/test-tts', { method: 'POST', body: '{}' }),
  listJobs: () => req<Job[]>('/api/jobs'),
  getJob: (id: string) => req<Job>(`/api/jobs/${id}`),
  createJob: (body: { title: string; prompt_user?: string; series?: string }) =>
    req<Job>('/api/jobs', { method: 'POST', body: JSON.stringify(body) }),
  updateJob: (id: string, body: unknown) =>
    req<Job>(`/api/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteJob: (id: string) => req<{ ok: boolean }>(`/api/jobs/${id}`, { method: 'DELETE' }),
  runJob: (id: string, from_stage?: StageName) =>
    req<{ ok: boolean }>(`/api/jobs/${id}/run`, {
      method: 'POST',
      body: JSON.stringify(from_stage ? { from_stage } : {}),
    }),
  cancelJob: (id: string) => req<{ ok: boolean }>(`/api/jobs/${id}/cancel`, { method: 'POST', body: '{}' }),
  getScript: (id: string) => req<{ text: string }>(`/api/jobs/${id}/script`),
  listPresets: () =>
    req<Array<{ id: string; name: string; prompt_system: string; prompt_user_template: string }>>(
      '/api/presets',
    ),
  libraryClips: () => req<Array<{ path: string; name: string; size_bytes: number }>>('/api/library/clips'),
  async uploadClip(id: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`/api/jobs/${id}/upload-clip`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error(await res.text())
    return res.json() as Promise<{ path: string; job: Job }>
  },
  async uploadThumbSource(id: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`/api/jobs/${id}/upload-thumb-source`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error(await res.text())
    return res.json() as Promise<{ path: string; job: Job }>
  },
  thumbPreviewUrl(params: Record<string, string>) {
    // Use POST via blob helper instead for body — kept for completeness
    return params
  },
  async previewThumbnail(body: {
    headline: string
    subheadline?: string
    text_color?: string
    accent_color?: string
    source_image_path?: string
  }) {
    const res = await fetch('/api/thumbnails/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await res.text())
    return URL.createObjectURL(await res.blob())
  },
}
