// API client. All requests go through Next's `/api/*` rewrite to the FastAPI backend.

const BASE = "/api";

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
  text_overlay_id?: string | null;
  rendered_text_overlay?: string | null;
  is_generated: boolean;
  source_upload_id?: string | null;
};

export type Storyboard = {
  storyboard_id: string;
  project_id: string;
  template_id: string;
  shots: ResolvedShot[];
  audio_cues: Template["audio_cues"];
  text_overlays: Template["text_overlays"];
  total_duration_sec: number;
  aspect_ratio: string;
  generated_slot_ids: string[];
  unfilled_slot_ids: string[];
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
  generateStoryboard: (projectId: string, templateId: string) =>
    request<Storyboard>(`/projects/${projectId}/storyboard`, {
      method: "POST",
      body: JSON.stringify({ template_id: templateId, use_audio_for_pacing: false }),
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

  // audio
  listTracks: () => request<AudioTrack[]>("/audio"),

  // styles
  listStyles: (category?: string) =>
    request<VideoStyle[]>(`/styles${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  listStyleCategories: () => request<string[]>("/styles/categories"),
  getStyle: (styleId: string) => request<VideoStyle>(`/styles/${styleId}`),
};
