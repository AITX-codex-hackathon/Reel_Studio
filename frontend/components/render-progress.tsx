"use client";

import { Download, Film, Loader2, Maximize2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { RenderJob } from "@/lib/api";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  projectId: string;
  job: RenderJob;
  liveProgress?: number;
  liveMessage?: string;
  livePhase?: string;
}

export function RenderProgressCard({ projectId, job, liveProgress, liveMessage, livePhase }: Props) {
  const [instagramOpen, setInstagramOpen] = useState(false);
  const progressPct = (liveProgress ?? job.progress) * 100;
  const isQueued = job.status === "pending";
  const isRunning = job.status === "running";
  const isActive = isQueued || isRunning;
  const isDone = job.status === "succeeded";
  const isError = job.status === "failed";
  const isInstagram = job.pass_type.startsWith("instagram_");
  const isDraft = job.pass_type.endsWith("draft");
  const videoUrl = api.renderFileUrl(projectId, job.id);

  return (
    <div
      className={cn(
        "rounded-2xl border p-5 transition-colors",
        isDone
          ? "border-emerald-200 bg-emerald-50/40"
          : isError
            ? "border-red-200 bg-red-50/40"
            : "border-border/60 bg-white",
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center",
            isDone
              ? "bg-emerald-100 text-emerald-700"
              : isError
                ? "bg-red-100 text-red-700"
                : "bg-gradient-brand text-white",
          )}
        >
          {isActive ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Film className="w-5 h-5" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">
            {isInstagram
              ? isDraft ? "Instagram Reel draft" : "Instagram Reel final"
              : isDraft ? "Horizontal draft" : "Horizontal final"}
          </div>
          <div className="text-xs text-ink-subtle">
            {isQueued && "Queued"}
            {isRunning && `${Math.round(progressPct)}% — ${liveMessage || "rendering…"}`}
            {isDone && (isInstagram ? "9:16 reel ready" : "16:9 preview ready")}
            {isError && "Failed"}
          </div>
        </div>
        {isDone && isInstagram && (
          <Button size="sm" variant="secondary" onClick={() => setInstagramOpen(true)}>
            <Maximize2 className="w-4 h-4" /> Open Reel
          </Button>
        )}
        {isDone && (
          <Button asChild size="sm" variant="default">
            <Link href={videoUrl} target="_blank" download>
              <Download className="w-4 h-4" /> {isInstagram ? "Download Reel" : "Download"}
            </Link>
          </Button>
        )}
      </div>

      {isActive && (
        <div className="mt-4 space-y-2">
          {(liveMessage || livePhase) && (
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="text-ink-muted truncate">{liveMessage || "Working…"}</span>
              {livePhase && (
                <span className="shrink-0 rounded-full bg-primary-50 px-2 py-0.5 font-medium text-primary-700">
                  {livePhase}
                </span>
              )}
            </div>
          )}
          <Progress value={progressPct} />
        </div>
      )}

      {isDone && (
        <div className="mt-4 flex justify-center rounded-lg border border-border/50 bg-ink p-3">
          <video
            controls
            preload="metadata"
            playsInline
            className={cn(
              "max-h-[70vh] max-w-full rounded-md bg-black object-cover",
              isInstagram ? "aspect-[9/16] w-auto" : "aspect-video w-full",
            )}
            src={videoUrl}
          />
        </div>
      )}

      {instagramOpen && isInstagram && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="flex max-h-[92vh] w-full max-w-4xl flex-col rounded-lg bg-white shadow-2xl">
            <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
              <div>
                <div className="text-sm font-semibold">Instagram Reel Preview</div>
                <div className="text-xs text-ink-subtle">9:16 vertical, ready to post</div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setInstagramOpen(false)} aria-label="Close Instagram preview">
                <X className="w-4 h-4" />
              </Button>
            </div>
            <div className="flex min-h-0 flex-1 justify-center bg-ink p-4">
              <video
                controls
                autoPlay
                preload="metadata"
                playsInline
                className="aspect-[9/16] max-h-[80vh] w-auto max-w-full rounded-md bg-black object-cover"
                src={videoUrl}
              />
            </div>
          </div>
        </div>
      )}

      {isError && job.error && (
        <pre className="mt-3 text-xs text-red-700 bg-red-50 rounded-lg p-3 overflow-auto whitespace-pre-wrap">
          {job.error}
        </pre>
      )}
    </div>
  );
}
