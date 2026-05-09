// WebSocket client for render progress.

export type ProgressMessage = {
  render_id: string;
  pass_type: "draft" | "final";
  progress?: number;
  seconds_done?: number;
  fps?: number;
  status?: "succeeded" | "failed";
  output_url?: string;
  error?: string;
};

export function connectProgressWS(
  projectId: string,
  onMessage: (m: ProgressMessage) => void,
): () => void {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const url = apiBase.replace(/^http/, "ws") + `/ws/projects/${projectId}/progress`;
  let ws: WebSocket | null = null;
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const open = () => {
    ws = new WebSocket(url);
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
