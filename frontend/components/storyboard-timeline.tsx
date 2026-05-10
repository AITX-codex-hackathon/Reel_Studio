"use client";

import { useCallback, useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Sparkles, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Storyboard, Upload } from "@/lib/api";
import { api } from "@/lib/api";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  storyboard: Storyboard;
  uploads: Upload[];
  onUpdate?: (updated: Storyboard) => void;
}

export function StoryboardTimeline({ storyboard, uploads, onUpdate }: Props) {
  const [shots, setShots] = useState(storyboard.shots);
  const [saving, setSaving] = useState(false);

  const uploadById = new Map(uploads.map((u) => [u.id, u]));

  const swap = useCallback(
    async (i: number, j: number) => {
      const next = [...shots];
      [next[i], next[j]] = [next[j], next[i]];

      // Recalculate start times
      let cursor = 0;
      const resequenced = next.map((s) => {
        const updated = { ...s, start_time_sec: cursor };
        cursor += s.duration_sec;
        return updated;
      });

      setShots(resequenced);
      setSaving(true);
      try {
        const updated: Storyboard = { ...storyboard, shots: resequenced };
        const saved = await api.saveStoryboard(storyboard.project_id, updated);
        onUpdate?.(saved);
      } finally {
        setSaving(false);
      }
    },
    [shots, storyboard, onUpdate],
  );

  const totalDuration = shots.reduce((sum, s) => sum + s.duration_sec, 0);

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Duration" value={formatSeconds(totalDuration)} />
        <Stat label="Shots" value={String(shots.length)} />
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
              Upload more matching photos or enable a generative provider.
            </p>
          </div>
        </div>
      )}

      {storyboard.notes && (
        <p className="text-sm text-ink-muted italic">{storyboard.notes}</p>
      )}

      {saving && (
        <p className="text-xs text-ink-muted">Saving order…</p>
      )}

      {/* Horizontal scrollable strip */}
      <div className="overflow-x-auto pb-2">
        <div className="flex gap-3 min-w-max">
          {shots.map((shot, i) => {
            const upload = shot.source_upload_id
              ? uploadById.get(shot.source_upload_id)
              : null;
            const imgUrl = upload ? api.uploadFileUrl(upload.id) : null;

            return (
              <div
                key={shot.slot_id + i}
                className="flex flex-col items-center gap-1 w-36 shrink-0"
              >
                {/* Thumbnail card */}
                <div className="relative w-36 h-48 rounded-xl overflow-hidden border border-border/60 bg-gradient-soft flex items-center justify-center">
                  {imgUrl ? (
                    <img
                      src={imgUrl}
                      className="w-full h-full object-cover"
                      alt={shot.slot_id}
                      loading="lazy"
                    />
                  ) : (
                    <Sparkles className="w-6 h-6 text-primary/40" />
                  )}
                  {/* Shot number badge */}
                  <div className="absolute top-2 left-2 w-6 h-6 rounded-full bg-black/60 text-white text-xs font-bold flex items-center justify-center">
                    {i + 1}
                  </div>
                  {shot.is_generated && (
                    <div className="absolute top-2 right-2">
                      <Badge variant="accent" className="text-[10px] px-1.5">
                        <Wand2 className="w-2.5 h-2.5" /> AI
                      </Badge>
                    </div>
                  )}
                </div>

                {/* Metadata */}
                <div className="w-full space-y-0.5 text-center">
                  <p className="text-xs font-medium truncate text-ink">{shot.slot_id}</p>
                  <p className="text-[11px] text-ink-subtle">{shot.duration_sec.toFixed(1)}s</p>
                  <Badge variant="muted" className="text-[10px]">
                    {shot.motion}
                  </Badge>
                </div>

                {/* Swap buttons */}
                <div className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    className={cn("w-7 h-7", i === 0 && "invisible")}
                    disabled={i === 0 || saving}
                    onClick={() => swap(i, i - 1)}
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className={cn("w-7 h-7", i === shots.length - 1 && "invisible")}
                    disabled={i === shots.length - 1 || saving}
                    onClick={() => swap(i, i + 1)}
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
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
