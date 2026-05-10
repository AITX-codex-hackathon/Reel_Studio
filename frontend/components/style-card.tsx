"use client";

import { Camera, Wind } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { VideoStyle } from "@/lib/api";
import { cn } from "@/lib/utils";

const CATEGORY_COLORS: Record<string, string> = {
  "Drone Aerial":    "bg-sky-100 text-sky-700 border-sky-200",
  "Dolly Interior":  "bg-violet-100 text-violet-700 border-violet-200",
  "Dolly Exterior":  "bg-purple-100 text-purple-700 border-purple-200",
  "Sunset/Twilight": "bg-orange-100 text-orange-700 border-orange-200",
  "Lighting Logic":  "bg-yellow-100 text-yellow-700 border-yellow-200",
  "Macro/Detail":    "bg-emerald-100 text-emerald-700 border-emerald-200",
  "High-Energy":     "bg-rose-100 text-rose-700 border-rose-200",
  "Seamless Bridge": "bg-slate-100 text-slate-700 border-slate-200",
};

const CATEGORY_ACCENT: Record<string, string> = {
  "Drone Aerial":    "from-sky-400/20 to-blue-400/10",
  "Dolly Interior":  "from-violet-400/20 to-purple-400/10",
  "Dolly Exterior":  "from-purple-400/20 to-fuchsia-400/10",
  "Sunset/Twilight": "from-orange-400/20 to-amber-400/10",
  "Lighting Logic":  "from-yellow-400/20 to-amber-400/10",
  "Macro/Detail":    "from-emerald-400/20 to-green-400/10",
  "High-Energy":     "from-rose-400/20 to-red-400/10",
  "Seamless Bridge": "from-slate-400/20 to-gray-400/10",
};

interface Props {
  style: VideoStyle;
  selected?: boolean;
  onSelect?: () => void;
}

export function StyleCard({ style, selected, onSelect }: Props) {
  const catColor = CATEGORY_COLORS[style.category] ?? "bg-primary-100 text-primary-700 border-primary-200";
  const accent = CATEGORY_ACCENT[style.category] ?? "from-primary-400/20 to-primary-400/10";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn("text-left w-full group focus:outline-none", selected && "scale-[0.99]")}
    >
      <Card
        className={cn(
          "h-full transition-all hover:shadow-brand-soft hover:-translate-y-0.5 overflow-hidden",
          selected && "ring-2 ring-primary border-primary shadow-brand",
        )}
      >
        {/* Gradient header band */}
        <div className={cn("h-16 bg-gradient-to-br relative", accent)}>
          <span className="absolute top-2 left-2 font-mono text-[10px] font-bold text-ink-subtle/60 tracking-wider">
            {style.style_id}
          </span>
          <span
            className={cn(
              "absolute top-2 right-2 text-[10px] font-medium px-2 py-0.5 rounded-full border",
              catColor,
            )}
          >
            {style.category}
          </span>
          <div className="absolute bottom-2 left-2">
            <span className="text-xs font-semibold text-ink/70">{style.mood}</span>
          </div>
        </div>

        <CardHeader className="py-3 px-4">
          <CardTitle className={cn("text-sm leading-snug", selected && "text-primary")}>
            {style.camera_motion}
          </CardTitle>
        </CardHeader>

        <CardContent className="px-4 pb-4 space-y-2">
          <div className="flex items-start gap-1.5 text-[11px] text-ink-muted">
            <Wind className="w-3 h-3 mt-0.5 shrink-0 text-primary/50" />
            <span className="line-clamp-1">{style.environmental_dynamics}</span>
          </div>

          <p className="text-[11px] text-ink-subtle line-clamp-3 leading-relaxed">
            {style.video_prompt}
          </p>
        </CardContent>
      </Card>
    </button>
  );
}
