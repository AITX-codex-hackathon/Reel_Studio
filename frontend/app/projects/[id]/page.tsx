"use client";

import { use, useEffect, useState } from "react";
import { Activity, ArrowRight, Check, Loader2, Radio, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RenderProgressCard } from "@/components/render-progress";
import { StoryboardTimeline } from "@/components/storyboard-timeline";
import { UploadDropzone } from "@/components/upload-dropzone";
import { MusicBrowser } from "@/components/music-browser";
import {
  api,
  type ProjectMusic,
  type Project,
  type RenderJob,
  type Storyboard,
  type Upload,
  type WorkflowSnapshotEvent,
} from "@/lib/api";
import { connectProgressWS, type WorkflowMessage } from "@/lib/ws";
import { cn } from "@/lib/utils";

type Step = "upload" | "music" | "storyboard" | "render";
type WorkflowEvent = WorkflowMessage & { id: string; at: number };

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const [project, setProject] = useState<Project | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [renders, setRenders] = useState<RenderJob[]>([]);
  const [currentMusic, setCurrentMusic] = useState<ProjectMusic | null>(null);
  const [step, setStep] = useState<Step>("upload");

  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);
  const [storyboardDirty, setStoryboardDirty] = useState(false);
  const [savingStoryboard, setSavingStoryboard] = useState(false);

  const [liveProgress, setLiveProgress] = useState<Record<string, number>>({});
  const [renderMessages, setRenderMessages] = useState<Record<string, string>>({});
  const [renderPhases, setRenderPhases] = useState<Record<string, string>>({});
  const [workflowEvents, setWorkflowEvents] = useState<WorkflowEvent[]>([]);

  // Initial load
  useEffect(() => {
    Promise.all([
      api.getProject(projectId),
      api.listUploads(projectId),
      api.getStoryboard(projectId),
      api.listRenders(projectId),
      api.getCurrentMusic(projectId),
    ]).then(([p, u, s, r, m]) => {
      setProject(p);
      setUploads((current) => (
        current.length > 0 && u.length === 0 ? current : mergeUploads(current, u)
      ));
      if (s) setStoryboard(s);
      if (s) setStoryboardDirty(false);
      setRenders(r);
      setCurrentMusic(m);
      // pick the most advanced step
      if (r.length) setStep("render");
      else if (s) setStep("storyboard");
      else if (m) setStep("music");
      else if (u.length) setStep("music");
    });
  }, [projectId]);

  // WebSocket: live workflow/render progress
  useEffect(() => {
    const applyMessage = (msg: WorkflowMessage, mode: "append" | "snapshot" = "append") => {
      if (msg.message || msg.status === "failed" || msg.status === "succeeded") {
        const event = toWorkflowEvent(msg);
        setWorkflowEvents((events) => (
          mode === "snapshot"
            ? [event, ...events].slice(0, 10)
            : [event, ...events].slice(0, 10)
        ));
      }
      const renderId = msg.render_id;
      if (renderId && msg.progress != null) {
        setLiveProgress((prev) => ({ ...prev, [renderId]: msg.progress! }));
      }
      if (renderId && msg.message) {
        setRenderMessages((prev) => ({ ...prev, [renderId]: msg.message! }));
      }
      if (renderId && msg.phase) {
        setRenderPhases((prev) => ({ ...prev, [renderId]: msg.phase! }));
      }
      if (msg.status === "succeeded" || msg.status === "failed") {
        api.listRenders(projectId).then(setRenders);
      }
    };

    const catchUp = () => {
      api.getWorkflowCurrent(projectId)
        .then((snapshot) => {
          const events = snapshot.events
            .filter((event) => event.message || event.status === "failed" || event.status === "succeeded")
            .map(toWorkflowEvent)
            .slice(0, 10);
          setWorkflowEvents(events);
          for (const event of snapshot.events) {
            const renderId = event.render_id;
            if (renderId && event.progress != null) {
              setLiveProgress((prev) => ({ ...prev, [renderId]: event.progress! }));
            }
            if (renderId && event.message) {
              setRenderMessages((prev) => ({ ...prev, [renderId]: event.message! }));
            }
            if (renderId && event.phase) {
              setRenderPhases((prev) => ({ ...prev, [renderId]: event.phase! }));
            }
          }
        })
        .catch(() => {});
    };

    catchUp();
    const close = connectProgressWS(projectId, (msg: WorkflowMessage) => applyMessage(msg), catchUp);
    return close;
  }, [projectId]);

  const onGenerateStoryboard = async () => {
    setGeneratingStoryboard(true);
    pushLocalEvent("storyboard", "Analyzing photos...");
    try {
      const sb = await api.generateStoryboard(projectId);
      setStoryboard(sb);
      setStoryboardDirty(false);
      setStep("storyboard");
    } catch (e) {
      pushLocalEvent("storyboard", `Storyboard failed: ${e instanceof Error ? e.message : e}`, "failed");
      const savedStoryboard = await api.getStoryboard(projectId).catch(() => null);
      if (savedStoryboard) {
        setStoryboard(savedStoryboard);
        setStoryboardDirty(false);
        setStep("storyboard");
        return;
      }
      alert(`Failed to generate storyboard: ${e instanceof Error ? e.message : e}`);
    } finally {
      setGeneratingStoryboard(false);
    }
  };

  const onRender = async (passType: "draft" | "final") => {
    try {
      if (storyboard && storyboardDirty) {
        await onSaveStoryboard(storyboard);
      }
      pushLocalEvent("render", `${passType === "draft" ? "Draft" : "Final"} render queued.`);
      const job = await api.startRender(projectId, passType);
      setRenders((rs) => [job, ...rs]);
      setStep("render");
    } catch (e) {
      pushLocalEvent("render", `Render failed to start: ${e instanceof Error ? e.message : e}`, "failed");
      alert(`Render failed to start: ${e instanceof Error ? e.message : e}`);
    }
  };

  const onStoryboardChange = (next: Storyboard) => {
    setStoryboard(next);
    setStoryboardDirty(true);
  };

  const onSaveStoryboard = async (storyboardToSave = storyboard) => {
    if (!storyboardToSave) return;
    setSavingStoryboard(true);
    try {
      const saved = await api.saveStoryboard(projectId, storyboardToSave);
      setStoryboard(saved);
      setStoryboardDirty(false);
      pushLocalEvent("storyboard", "Storyboard edits saved.", "succeeded");
    } catch (e) {
      pushLocalEvent("storyboard", `Storyboard save failed: ${e instanceof Error ? e.message : e}`, "failed");
      throw e;
    } finally {
      setSavingStoryboard(false);
    }
  };

  const pushLocalEvent = (
    stage: string,
    message: string,
    status: WorkflowMessage["status"] = "running",
  ) => {
    const event: WorkflowEvent = {
      id: `${Date.now()}-${Math.random()}`,
      at: Date.now(),
      type: "workflow",
      stage,
      message,
      status,
    };
    setWorkflowEvents((events) => [
      event,
      ...events,
    ].slice(0, 10));
  };

  if (!project) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <Link href="/" className="text-sm text-ink-muted hover:text-primary">
            ← All projects
          </Link>
          <h1 className="font-display text-3xl font-bold mt-2">{project.name}</h1>
          {project.address && (
            <p className="text-ink-muted mt-1">{project.address}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {project.beds && <Badge variant="outline">{project.beds} BD</Badge>}
          {project.baths && <Badge variant="outline">{project.baths} BA</Badge>}
          {project.sqft && (
            <Badge variant="outline">{project.sqft.toLocaleString()} sqft</Badge>
          )}
          {project.price && <Badge variant="accent">{project.price}</Badge>}
        </div>
      </div>

      {/* Stepper */}
      <Stepper
        step={step}
        onSelect={setStep}
        hasUploads={uploads.length > 0}
        hasMusic={!!currentMusic}
        hasStoryboard={!!storyboard}
      />

      <WorkflowTelemetry events={workflowEvents} />

      {/* Step content */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload property photos</CardTitle>
            <CardDescription>
              Drop 50–150 images — exterior, interior, details. Higher quality photos
              produce better reels.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <UploadDropzone
              projectId={projectId}
              uploads={uploads}
              onChange={setUploads}
            />
          </CardContent>
          <div className="flex justify-end p-6 border-t border-border/40">
            <Button
              onClick={() => setStep("music")}
              disabled={uploads.length === 0}
            >
              Choose music <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>
      )}

      {step === "music" && (
        <Card>
          <CardHeader>
            <CardTitle>Choose music</CardTitle>
            <CardDescription>
              Search the Free To Use catalog. Insert prepares beat timestamps and audio cuts for the reel.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MusicBrowser
              projectId={projectId}
              currentMusic={currentMusic}
              onInserted={setCurrentMusic}
            />
          </CardContent>
          <div className="flex justify-between gap-3 p-6 border-t border-border/40">
            <Button variant="ghost" onClick={() => setStep("upload")}>
              ← Back
            </Button>
            <Button
              onClick={onGenerateStoryboard}
              disabled={!currentMusic || generatingStoryboard}
            >
              {generatingStoryboard ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating storyboard…
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  Generate storyboard
                </>
              )}
            </Button>
          </div>
        </Card>
      )}

      {step === "storyboard" && storyboard && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between">
            <div>
              <CardTitle>Storyboard</CardTitle>
              <CardDescription>
                Reorder the horizontal sequence, inspect the AI prompts, and edit any scene that needs a different style, transition, or camera direction.
              </CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={onGenerateStoryboard}
              disabled={generatingStoryboard || uploads.length === 0}
            >
              {generatingStoryboard ? "…" : "Regenerate"}
            </Button>
          </CardHeader>
          <CardContent>
            <StoryboardTimeline
              storyboard={storyboard}
              uploads={uploads}
              editable
              dirty={storyboardDirty}
              saving={savingStoryboard}
              onChange={onStoryboardChange}
              onSave={onSaveStoryboard}
            />
          </CardContent>
          <div className="flex justify-between gap-3 p-6 border-t border-border/40">
            <Button variant="ghost" onClick={() => setStep("music")}>
              ← Back to music
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onRender("draft")} disabled={savingStoryboard}>
                <Sparkles className="w-4 h-4" /> Render draft
              </Button>
              <Button onClick={() => onRender("final")} disabled={savingStoryboard}>
                Render final <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {step === "render" && (
        <Card>
          <CardHeader>
            <CardTitle>Renders</CardTitle>
            <CardDescription>
              Drafts are 540p with a watermark. Finals are 1080p, ready for Instagram.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => onRender("draft")}>
                <Sparkles className="w-4 h-4" /> New draft
              </Button>
              <Button onClick={() => onRender("final")}>New final render</Button>
            </div>
            {renders.length === 0 ? (
              <p className="text-sm text-ink-muted">No renders yet — start one above.</p>
            ) : (
              <div className="space-y-3">
                {renders.map((r) => (
                  <RenderProgressCard
                    key={r.id}
                    projectId={projectId}
                    job={r}
                    liveProgress={liveProgress[r.id]}
                    liveMessage={renderMessages[r.id]}
                    livePhase={renderPhases[r.id]}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function toWorkflowEvent(message: WorkflowMessage | WorkflowSnapshotEvent): WorkflowEvent {
  const createdAt = message.created_at ? message.created_at * 1000 : Date.now();
  return {
    ...message,
    id: `${createdAt}-${message.render_id || message.stage || message.phase || "workflow"}-${Math.random()}`,
    at: createdAt,
  };
}

function mergeUploads(current: Upload[], incoming: Upload[]) {
  const byId = new Map<string, Upload>();
  for (const upload of current) byId.set(upload.id, upload);
  for (const upload of incoming) byId.set(upload.id, upload);
  return Array.from(byId.values());
}

function Stepper({
  step,
  onSelect,
  hasUploads,
  hasMusic,
  hasStoryboard,
}: {
  step: Step;
  onSelect: (s: Step) => void;
  hasUploads: boolean;
  hasMusic: boolean;
  hasStoryboard: boolean;
}) {
  const items: { step: Step; label: string; done: boolean }[] = [
    { step: "upload", label: "Upload", done: hasUploads },
    { step: "music", label: "Music", done: hasMusic },
    { step: "storyboard", label: "Storyboard", done: hasStoryboard },
    { step: "render", label: "Render", done: false },
  ];
  return (
    <div className="flex items-stretch gap-2">
      {items.map((it, i) => {
        const isCurrent = it.step === step;
        const isUnlocked =
          i === 0 ||
          (i === 1 && hasUploads) ||
          (i === 2 && hasMusic) ||
          (i === 3 && hasStoryboard);
        return (
          <button
            key={it.step}
            onClick={() => isUnlocked && onSelect(it.step)}
            disabled={!isUnlocked}
            className={cn(
              "flex-1 rounded-2xl border px-4 py-3 text-left transition-all",
              isCurrent
                ? "border-primary bg-gradient-soft shadow-brand-soft"
                : isUnlocked
                  ? "border-border/60 bg-white hover:border-primary-200"
                  : "border-border/40 bg-white/40 opacity-50 cursor-not-allowed",
            )}
          >
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold",
                  it.done
                    ? "bg-emerald-100 text-emerald-700"
                    : isCurrent
                      ? "bg-gradient-brand text-white"
                      : "bg-primary-100 text-primary-700",
                )}
              >
                {it.done ? <Check className="w-3.5 h-3.5" /> : i + 1}
              </div>
              <span className="text-sm font-medium">{it.label}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function WorkflowTelemetry({ events }: { events: WorkflowEvent[] }) {
  if (events.length === 0) return null;
  const latest = events[0];
  return (
    <div className="rounded-2xl border border-primary-100 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-primary-50 text-primary-700">
          {latest.status === "running" || latest.status === "queued" ? (
            <Radio className="h-4 w-4" />
          ) : (
            <Activity className="h-4 w-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium text-ink">
              {latest.message || "Working…"}
            </p>
            {(latest.stage || latest.phase) && (
              <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700">
                {latest.phase || latest.stage}
              </span>
            )}
          </div>
          <div className="mt-2 grid gap-1">
            {events.slice(1, 4).map((event) => (
              <div key={event.id} className="flex items-center gap-2 text-xs text-ink-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-primary-300" />
                <span className="truncate">{event.message}</span>
              </div>
            ))}
          </div>
        </div>
        {typeof latest.progress === "number" && (
          <div className="shrink-0 text-sm font-semibold text-primary-700">
            {Math.round(latest.progress * 100)}%
          </div>
        )}
      </div>
    </div>
  );
}
