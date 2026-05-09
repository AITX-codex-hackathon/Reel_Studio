"use client";

import { Clock, Film, Music2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Template } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  template: Template;
  selected?: boolean;
  onSelect?: () => void;
}

export function TemplateCard({ template, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "text-left w-full group focus:outline-none",
        selected && "scale-[0.99]",
      )}
    >
      <Card
        className={cn(
          "transition-all hover:shadow-brand-soft hover:-translate-y-0.5",
          selected && "ring-2 ring-primary border-primary shadow-brand",
        )}
      >
        <div
          className={cn(
            "h-32 flex items-center justify-center relative overflow-hidden",
            selected ? "bg-gradient-brand" : "bg-gradient-soft",
          )}
        >
          <Film
            className={cn(
              "w-12 h-12 transition-transform group-hover:scale-110",
              selected ? "text-white" : "text-primary/50",
            )}
          />
          <div className="absolute top-2 right-2 flex gap-1">
            <Badge variant={selected ? "muted" : "default"} className="text-[10px]">
              {template.aspect_ratio}
            </Badge>
          </div>
        </div>
        <CardHeader>
          <CardTitle className={cn("text-lg", selected && "text-primary")}>
            {template.name}
          </CardTitle>
          <CardDescription className="line-clamp-2">
            {template.description}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5 text-xs text-ink-muted">
            <span className="inline-flex items-center gap-1">
              <Clock className="w-3 h-3" /> {template.target_duration_sec}s
            </span>
            <span>·</span>
            <span>{template.shot_slots.length} shots</span>
            <span>·</span>
            <span className="inline-flex items-center gap-1">
              <Music2 className="w-3 h-3" /> {template.pacing_mode}
            </span>
          </div>
        </CardContent>
      </Card>
    </button>
  );
}
