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
  const isQueued = job.status === "pending";
  const isRunning = job.status === "running";
  const isActive = isQueued || isRunning;
  const isDone = job.status === "succeeded";
  const isError = job.status === "failed";

  return (
    <div
      className={cn(
        "rounded-2xl border p-5 transition-colors",
        isDone
          ? "border-emerald-800/40 bg-emerald-900/20"
          : isError
            ? "border-red-800/40 bg-red-900/20"
            : "border-white/[0.08] bg-[#14141f]",
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-10 h-10 rounded-xl flex items-center justify-center",
            isDone
              ? "bg-emerald-900/40 text-emerald-400"
              : isError
                ? "bg-red-900/40 text-red-400"
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
            {job.pass_type === "draft" ? "Draft preview" : "Final render"}
          </div>
          <div className="text-xs text-ink-subtle">
            {isQueued && "Queued"}
            {isRunning && `${Math.round(progressPct)}% — encoding…`}
            {isDone && "Ready"}
            {isError && "Failed"}
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

      {isActive && (
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
        <pre className="mt-3 text-xs text-red-400 bg-red-900/20 rounded-lg p-3 overflow-auto whitespace-pre-wrap">
          {job.error}
        </pre>
      )}
    </div>
  );
}
