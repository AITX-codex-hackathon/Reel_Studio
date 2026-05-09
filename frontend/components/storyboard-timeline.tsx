"use client";

import { Sparkles, AlertTriangle, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Storyboard, Upload } from "@/lib/api";
import { api } from "@/lib/api";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  storyboard: Storyboard;
  uploads: Upload[];
}

export function StoryboardTimeline({ storyboard, uploads }: Props) {
  const uploadById = new Map(uploads.map((u) => [u.id, u]));

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Duration" value={formatSeconds(storyboard.total_duration_sec)} />
        <Stat label="Shots" value={String(storyboard.shots.length)} />
        <Stat
          label="Generated"
          value={String(storyboard.generated_slot_ids.length)}
          icon={<Wand2 className="w-3.5 h-3.5" />}
          accent
        />
        <Stat
          label="Unfilled"
          value={String(storyboard.unfilled_slot_ids.length)}
          warning={storyboard.unfilled_slot_ids.length > 0}
        />
      </div>

      {storyboard.unfilled_slot_ids.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 flex gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-amber-900">
              {storyboard.unfilled_slot_ids.length} slot
              {storyboard.unfilled_slot_ids.length === 1 ? "" : "s"} couldn't be filled
            </p>
            <p className="text-amber-800/80 mt-0.5">
              Either upload more matching photos or enable a generative provider
              (set <code className="bg-amber-100 px-1 rounded">GEMINI_API_KEY</code> for Nano Banana Pro).
            </p>
          </div>
        </div>
      )}

      {/* Notes */}
      {storyboard.notes && (
        <p className="text-sm text-ink-muted italic">{storyboard.notes}</p>
      )}

      {/* Timeline */}
      <div className="space-y-2">
        {storyboard.shots.map((shot, i) => {
          const upload = shot.source_upload_id
            ? uploadById.get(shot.source_upload_id)
            : null;
          const imgUrl = upload
            ? api.uploadFileUrl(upload.id)
            : null; // generated images live on backend disk; we don't expose them by URL in v1
          return (
            <div
              key={shot.slot_id + i}
              className="flex items-stretch gap-3 rounded-xl border border-border/60 bg-white p-2 hover:border-primary-200 transition-colors"
            >
              <div className="w-10 text-center font-display font-semibold text-ink-subtle pt-2">
                {i + 1}
              </div>
              <div
                className={cn(
                  "w-24 h-16 rounded-lg overflow-hidden flex items-center justify-center bg-gradient-soft border border-border/40 shrink-0",
                )}
              >
                {imgUrl ? (
                  <img
                    src={imgUrl}
                    className="w-full h-full object-cover"
                    alt={shot.slot_id}
                    loading="lazy"
                  />
                ) : (
                  <Sparkles className="w-5 h-5 text-primary/50" />
                )}
              </div>
              <div className="flex-1 min-w-0 py-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm">{shot.slot_id}</span>
                  {shot.is_generated && (
                    <Badge variant="accent" className="text-[10px]">
                      <Wand2 className="w-2.5 h-2.5" /> AI
                    </Badge>
                  )}
                  <Badge variant="muted" className="text-[10px]">
                    {shot.motion}
                  </Badge>
                  {shot.text_overlay_id && shot.rendered_text_overlay && (
                    <Badge variant="default" className="text-[10px]">
                      “{shot.rendered_text_overlay.slice(0, 30)}{shot.rendered_text_overlay.length > 30 ? "…" : ""}”
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-ink-subtle mt-1">
                  {formatSeconds(shot.start_time_sec)} → {formatSeconds(shot.start_time_sec + shot.duration_sec)} · {shot.duration_sec.toFixed(1)}s · {shot.transition_in}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
  warning,
  icon,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warning?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-white p-3",
        warning ? "border-amber-200 bg-amber-50" : "border-border/60",
      )}
    >
      <div className="text-xs text-ink-muted flex items-center gap-1">
        {icon}
        {label}
      </div>
      <div
        className={cn(
          "font-display text-xl font-semibold mt-0.5",
          accent && "gradient-text",
          warning && "text-amber-700",
        )}
      >
        {value}
      </div>
    </div>
  );
}
