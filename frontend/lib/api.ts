// API client. Call FastAPI directly; long-running generation requests can outlive
// the Next dev rewrite proxy and surface as false 500s while the backend keeps running.

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Types ----
export type Project = {
  id: string;
  name: string;
  address?: string;
  price?: string;
  beds?: number;
  baths?: number;
  sqft?: number;
  description?: string;
  template_id?: string;
  storyboard_id?: string;
  created_at: string;
  updated_at: string;
};

export type Upload = {
  id: string;
  project_id: string;
  filename: string;
  width: number;
  height: number;
  sha256: string;
  created_at: string;
};

export type ShotSlot = {
  slot_id: string;
  description: string;
  room_type?: string;
  duration_sec: number;
  motion: string;
  motion_strength: number;
  transition_in: string;
  must_fill: boolean;
  fallback_to_generated: boolean;
  generation_prompt?: string;
  text_overlay_id?: string | null;
};

export type Template = {
  template_id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  target_duration_sec: number;
  aspect_ratio: string;
  pacing_mode: string;
  shot_slots: ShotSlot[];
  audio_cues: Array<{ track_query: string; kind: string; start_time_sec: number; end_time_sec?: number | null }>;
  text_overlays: Array<{ overlay_id: string; text_template: string; position: string }>;
  global_color_grade?: string | null;
};

export type ResolvedShot = {
  slot_id: string;
  image_path: string;
  start_time_sec: number;
  duration_sec: number;
  motion: string;
  motion_strength: number;
  transition_in: string;
  color_grade?: string | null;
  text_overlay_id?: string | null;
  rendered_text_overlay?: string | null;
  is_generated: boolean;
  source_upload_id?: string | null;
  room_type?: string | null;
  style_recipe_id?: string | null;
  scene_purpose?: string | null;
  style_notes?: string | null;
  beat_plan?: string | null;
  masking_plan?: string | null;
  transition_plan?: string | null;
  continuity_notes?: string | null;
  rubric_plan?: Record<string, unknown> | null;
  style_recipe_prompt?: string | null;
};

export type StoryboardCreativeBrief = {
  concept_title: string;
  logline: string;
  visual_theme: string;
  emotional_arc: string;
  music_strategy: string;
  continuity_rules: string[];
};

export type Storyboard = {
  storyboard_id: string;
  project_id: string;
  template_id: string;
  shots: ResolvedShot[];
  audio_cues: Template["audio_cues"];
  text_overlays: Template["text_overlays"];
  music?: ProjectMusic | null;
  creative_brief?: StoryboardCreativeBrief | null;
  total_duration_sec: number;
  aspect_ratio: string;
  generated_slot_ids: string[];
  unfilled_slot_ids: string[];
  selected_upload_ids?: string[];
  rejected_upload_ids?: string[];
  photo_selection_notes?: string;
  notes: string;
};

export type RenderJob = {
  id: string;
  project_id: string;
  storyboard_id: string;
  pass_type: "draft" | "final";
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  output_path?: string | null;
  duration_sec?: number | null;
  error?: string | null;
  created_at: string;
  finished_at?: string | null;
};

export type AudioTrack = {
  name: string;
  relative_path: string;
  mood?: string;
  tempo?: string;
  tags: string[];
};

export type FreeMusicTrack = {
  id: string;
  title: string;
  artist: string;
  duration_sec?: number | null;
  genre?: string | null;
  tags: string[];
  thumbnail_url?: string | null;
  preview_url?: string | null;
};

export type ProjectMusic = {
  id: string;
  project_id: string;
  source: string;
  track_id: string;
  title: string;
  artist: string;
  duration_sec?: number | null;
  audio_path: string;
  metadata_path: string;
  timestamps_path: string;
  cuts_dir?: string | null;
  manifest_path: string;
  tempo?: number | null;
  beat_count: number;
  beat_timestamps_ms: number[];
  attribution: string;
  created_at: string;
};

export type MusicInsertJob = {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  message: string;
  result?: ProjectMusic | null;
  error?: string | null;
};

export type Health = {
  status: string;
  providers: Record<string, boolean>;
};

export type VideoStyle = {
  style_id: string;
  category: string;
  mood: string;
  camera_motion: string;
  environmental_dynamics: string;
  video_prompt: string;
};

export type WorkflowSnapshotEvent = {
  type?: "workflow" | "render";
  stage?: string;
  phase?: string;
  status?: "queued" | "running" | "succeeded" | "failed";
  message?: string;
  progress?: number;
  render_id?: string;
  pass_type?: "draft" | "final";
  current?: number;
  total?: number;
  shot_id?: string;
  error?: string;
  created_at?: number;
};

export type WorkflowSnapshot = {
  project_id: string;
  connected_clients: number;
  events: WorkflowSnapshotEvent[];
};

// ---- Endpoints ----
export const api = {
  health: () => request<Health>("/health"),

  // projects
  listProjects: () => request<Project[]>("/projects"),
  createProject: (body: Partial<Project>) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  updateProject: (id: string, body: Partial<Project>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),

  // templates
  listTemplates: () => request<Template[]>("/templates"),
  getTemplate: (id: string) => request<Template>(`/templates/${id}`),
  templateFromPrompt: (brief: string, name?: string, save = false) =>
    request<Template>("/templates/from-prompt", {
      method: "POST",
      body: JSON.stringify({ brief, name, save }),
    }),

  // uploads
  listUploads: (projectId: string) =>
    request<Upload[]>(`/projects/${projectId}/uploads`),
  uploadImages: async (projectId: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const res = await fetch(`${BASE}/projects/${projectId}/uploads`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as Upload[];
  },
  deleteUpload: (projectId: string, uploadId: string) =>
    request<void>(`/projects/${projectId}/uploads/${uploadId}`, { method: "DELETE" }),
  uploadFileUrl: (uploadId: string) => `${BASE}/uploads/${uploadId}/file`,

  // storyboard
  generateStoryboard: (projectId: string) =>
    request<Storyboard>(`/projects/${projectId}/storyboard`, {
      method: "POST",
      body: JSON.stringify({ use_audio_for_pacing: false }),
    }),
  getStoryboard: (projectId: string) =>
    request<Storyboard | null>(`/projects/${projectId}/storyboard`),
  saveStoryboard: (projectId: string, storyboard: Storyboard) =>
    request<Storyboard>(`/projects/${projectId}/storyboard`, {
      method: "PUT",
      body: JSON.stringify({ storyboard }),
    }),

  // render
  startRender: (projectId: string, passType: "draft" | "final") =>
    request<RenderJob>(`/projects/${projectId}/renders?pass_type=${passType}`, {
      method: "POST",
    }),
  listRenders: (projectId: string) =>
    request<RenderJob[]>(`/projects/${projectId}/renders`),
  renderFileUrl: (projectId: string, renderId: string) =>
    `${BASE}/projects/${projectId}/renders/${renderId}/file`,
  getWorkflowCurrent: (projectId: string) =>
    request<WorkflowSnapshot>(`/projects/${projectId}/workflow/current`),

  // audio
  listTracks: () => request<AudioTrack[]>("/audio"),

  // styles
  listStyles: (category?: string) =>
    request<VideoStyle[]>(`/styles${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  listStyleCategories: () => request<string[]>("/styles/categories"),
  getStyle: (styleId: string) => request<VideoStyle>(`/styles/${styleId}`),

  // Free To Use music
  listFreeMusicTracks: (query = "", limit = 20) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (query.trim()) params.set("query", query.trim());
    return request<FreeMusicTrack[]>(`/free-music/tracks?${params.toString()}`);
  },
  getCurrentMusic: (projectId: string) =>
    request<ProjectMusic | null>(`/projects/${projectId}/music/current`),
  insertMusic: (projectId: string, trackId: string) =>
    request<MusicInsertJob>(`/projects/${projectId}/music/insert`, {
      method: "POST",
      body: JSON.stringify({ track_id: trackId, make_cuts: true, include_tail: false }),
    }),
  getMusicInsertJob: (projectId: string, jobId: string) =>
    request<MusicInsertJob>(`/projects/${projectId}/music/jobs/${jobId}`),
  projectMusicFileUrl: (projectId: string) => `${BASE}/projects/${projectId}/music/file`,
};
