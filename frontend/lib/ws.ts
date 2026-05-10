// WebSocket client for project workflow progress.

export type ProgressMessage = {
  type?: "render" | "workflow";
  render_id: string;
  pass_type: "draft" | "final";
  progress?: number;
  seconds_done?: number;
  fps?: number;
  status?: "queued" | "running" | "succeeded" | "failed";
  stage?: string;
  phase?: string;
  message?: string;
  current?: number;
  total?: number;
  shot_id?: string;
  output_url?: string;
  error?: string;
};

export type WorkflowMessage = {
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

export function connectProgressWS(
  projectId: string,
  onMessage: (m: WorkflowMessage) => void,
  onOpen?: () => void,
): () => void {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const url = apiBase.replace(/^http/, "ws") + `/ws/projects/${projectId}/progress`;
  let ws: WebSocket | null = null;
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const open = () => {
    ws = new WebSocket(url);
    ws.onopen = () => {
      onOpen?.();
    };
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data));
      } catch {}
    };
    ws.onclose = () => {
      if (closed) return;
      retryTimer = setTimeout(open, 1500);
    };
    ws.onerror = () => {
      ws?.close();
    };
  };
  open();

  return () => {
    closed = true;
    if (retryTimer) clearTimeout(retryTimer);
    ws?.close();
  };
}
