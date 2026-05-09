"use client";

import { Download, Film, Loader2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { RenderJob } from "@/lib/api";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  projectId: string;
  job: RenderJob;
  liveProgress?: number;
}

export function RenderProgressCard({ projectId, job, liveProgress }: Props) {
  const progressPct = (liveProgress ?? job.progress) * 100;
  const isRunning = job.status === "running" || job.status === "pending";
  const isDone = job.status === "succeeded";
  const isError = job.status === "failed";

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
          {isRunning ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Film className="w-5 h-5" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">
            {job.pass_type === "draft" ? "Draft preview" : "Final render"}
          </div>
          <div className="text-xs text-ink-subtle">
            {isRunning && `${Math.round(progressPct)}% — encoding…`}
            {isDone && "Ready"}
            {isError && "Failed"}
            {job.status === "pending" && !liveProgress && "Queued"}
          </div>
        </div>
        {isDone && (
          <Button asChild size="sm" variant="default">
            <Link href={api.renderFileUrl(projectId, job.id)} target="_blank" download>
              <Download className="w-4 h-4" /> Download
            </Link>
          </Button>
        )}
      </div>

      {isRunning && (
        <div className="mt-4">
          <Progress value={progressPct} />
        </div>
      )}

      {isDone && (
        <div className="mt-4 rounded-lg overflow-hidden bg-black">
          <video
            controls
            preload="metadata"
            className="w-full max-h-[60vh]"
            src={api.renderFileUrl(projectId, job.id)}
          />
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
