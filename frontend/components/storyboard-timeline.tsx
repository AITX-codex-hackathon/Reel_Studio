"use client";

import { useCallback, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  Pencil,
  Save,
  Sparkles,
  Wand2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/input";
import type { ResolvedShot, Storyboard, Upload } from "@/lib/api";
import { api } from "@/lib/api";
import { cn, formatSeconds } from "@/lib/utils";

interface Props {
  storyboard: Storyboard;
  uploads: Upload[];
  editable?: boolean;
  dirty?: boolean;
  saving?: boolean;
  onChange?: (storyboard: Storyboard) => void;
  onSave?: (storyboard?: Storyboard) => void | Promise<void>;
}

const MOTIONS = [
  "slow_zoom_in",
  "slow_zoom_out",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
  "push_in",
  "pull_out",
  "static",
  "generative",
];


export function StoryboardTimeline({
  storyboard,
  uploads,
  editable,
  dirty,
  saving,
  onChange,
  onSave,
}: Props) {
  const [editingShotId, setEditingShotId] = useState<string | null>(null);
  const [savingOrder, setSavingOrder] = useState(false);
  const shots = storyboard.shots;

  const uploadById = useMemo(() => new Map(uploads.map((u) => [u.id, u])), [uploads]);
  const totalDuration = useMemo(
    () => shots.reduce((sum, shot) => sum + shot.duration_sec, 0),
    [shots],
  );

  const storyboardWithShots = useCallback(
    (nextShots: ResolvedShot[]) => {
      let cursor = 0;
      const resequenced = nextShots.map((shot) => {
        const next = { ...shot, start_time_sec: cursor };
        cursor += shot.duration_sec;
        return next;
      });
      return {
        ...storyboard,
        shots: resequenced,
        total_duration_sec: cursor || storyboard.total_duration_sec,
      };
    },
    [storyboard],
  );

  const updateShots = useCallback(
    (nextShots: ResolvedShot[]) => {
      const nextStoryboard = storyboardWithShots(nextShots);
      onChange?.(nextStoryboard);
      return nextStoryboard;
    },
    [onChange, storyboardWithShots],
  );

  const updateShot = (index: number, patch: Partial<ResolvedShot>) => {
    const nextShots = shots.map((shot, shotIndex) => (
      shotIndex === index ? { ...shot, ...patch } : shot
    ));
    updateShots(nextShots);
  };

  const swap = useCallback(
    async (i: number, j: number) => {
      if (!editable || i < 0 || j < 0 || i >= shots.length || j >= shots.length) return;
      const nextShots = [...shots];
      [nextShots[i], nextShots[j]] = [nextShots[j], nextShots[i]];
      const nextStoryboard = updateShots(nextShots);
      if (!onSave) return;
      setSavingOrder(true);
      try {
        await onSave(nextStoryboard);
      } finally {
        setSavingOrder(false);
      }
    },
    [editable, onSave, shots, updateShots],
  );

  const editingIndex = shots.findIndex((shot) => shot.slot_id === editingShotId);
  const editingShot = editingIndex >= 0 ? shots[editingIndex] : null;

  return (
    <div className="space-y-6">
      {editable && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-100 bg-primary-50/40 p-3">
          <p className="text-sm text-ink-muted">
            AI wrote the first prompt pass. Reorder scenes horizontally, then edit only the shots that need a different prompt, style, transition, or camera move.
          </p>
          <Button size="sm" onClick={() => onSave?.(storyboard)} disabled={!dirty || saving || savingOrder}>
            <Save className="w-3.5 h-3.5" />
            {saving || savingOrder ? "Saving..." : dirty ? "Save edits" : "Saved"}
          </Button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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

      {storyboard.selected_upload_ids && storyboard.selected_upload_ids.length > 0 && uploads.length > 20 && (
        <p className="text-sm text-ink-muted">
          AI curated {storyboard.selected_upload_ids.length} of {uploads.length} uploaded photos for this story.
          {storyboard.photo_selection_notes ? ` ${storyboard.photo_selection_notes}` : ""}
        </p>
      )}

      {storyboard.creative_brief && (
        <div className="rounded-xl border border-border/60 bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-ink">
            <Clapperboard className="h-4 w-4 text-primary" />
            {storyboard.creative_brief.concept_title}
          </div>
          <p className="mt-2 text-sm text-ink-muted">{storyboard.creative_brief.logline}</p>
          <div className="mt-3 grid gap-2 text-xs text-ink-subtle sm:grid-cols-2">
            <p>{storyboard.creative_brief.visual_theme}</p>
            <p>{storyboard.creative_brief.emotional_arc}</p>
          </div>
        </div>
      )}

      {storyboard.unfilled_slot_ids.length > 0 && (
        <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="text-sm">
            <p className="font-medium text-amber-900">
              {storyboard.unfilled_slot_ids.length} slot
              {storyboard.unfilled_slot_ids.length === 1 ? "" : "s"} could not be filled
            </p>
            <p className="mt-0.5 text-amber-800/80">
              Either upload more matching photos or enable FAL generation
              (set <code className="rounded bg-amber-100 px-1">FAL_API_KEY</code>).
            </p>
          </div>
        </div>
      )}

      {storyboard.notes && (
        <p className="text-sm italic text-ink-muted">{storyboard.notes}</p>
      )}

      {savingOrder && (
        <p className="text-xs text-ink-muted">Saving order...</p>
      )}

      <div className="overflow-x-auto pb-2">
        <div className="flex min-w-max gap-3">
          {shots.map((shot, i) => {
            const upload = shot.source_upload_id ? uploadById.get(shot.source_upload_id) : null;
            const imgUrl = upload ? api.uploadFileUrl(upload.id) : null;
            const isEditing = editingShotId === shot.slot_id;

            return (
              <div
                key={`${shot.slot_id}-${i}`}
                className={cn(
                  "flex w-44 shrink-0 flex-col gap-2 rounded-xl border bg-white p-2 transition-colors",
                  isEditing ? "border-primary-300 shadow-brand-soft" : "border-border/60",
                )}
              >
                <div className="relative flex h-56 w-full items-center justify-center overflow-hidden rounded-lg border border-border/40 bg-gradient-soft">
                  {imgUrl ? (
                    <img
                      src={imgUrl}
                      className="h-full w-full object-cover"
                      alt={shot.slot_id}
                      loading="lazy"
                    />
                  ) : (
                    <Sparkles className="h-6 w-6 text-primary/40" />
                  )}
                  <div className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-xs font-bold text-white">
                    {i + 1}
                  </div>
                  {shot.is_generated && (
                    <div className="absolute right-2 top-2">
                      <Badge variant="accent" className="px-1.5 text-[10px]">
                        <Wand2 className="h-2.5 w-2.5" /> AI
                      </Badge>
                    </div>
                  )}
                </div>

                <div className="space-y-1">
                  <p className="truncate text-xs font-medium text-ink">{shot.slot_id}</p>
                  <p className="text-[11px] text-ink-subtle">
                    {formatSeconds(shot.start_time_sec)} - {formatSeconds(shot.start_time_sec + shot.duration_sec)}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="muted" className="text-[10px]">{shot.motion}</Badge>
                    <Badge variant="muted" className="text-[10px]">{shot.transition_in}</Badge>
                    {shot.style_recipe_prompt && <Badge variant="default" className="text-[10px]">prompt</Badge>}
                  </div>
                  {shot.scene_purpose && (
                    <p className="text-[11px] leading-snug text-ink-muted">{shortText(shot.scene_purpose, 118)}</p>
                  )}
                </div>

                {editable && (
                  <div className="mt-auto flex items-center justify-between gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      className={cn("h-8 w-8", i === 0 && "invisible")}
                      disabled={i === 0 || saving || savingOrder}
                      onClick={() => swap(i, i - 1)}
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant={isEditing ? "secondary" : "outline"}
                      className="h-8 px-2 text-xs"
                      onClick={() => setEditingShotId(isEditing ? null : shot.slot_id)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      {isEditing ? "Close" : "Edit"}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className={cn("h-8 w-8", i === shots.length - 1 && "invisible")}
                      disabled={i === shots.length - 1 || saving || savingOrder}
                      onClick={() => swap(i, i + 1)}
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {editable && editingShot && (
        <div className="rounded-xl border border-primary-100 bg-white p-4">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-ink">Scene {editingIndex + 1}: {editingShot.slot_id}</p>
              <p className="text-xs text-ink-muted">
                Customize this AI prompt only if the scene needs a different style, transition, mask, or camera intention.
              </p>
            </div>
            {dirty && <Badge variant="accent">unsaved edits</Badge>}
          </div>
          <ShotEditor
            key={editingShot.slot_id}
            shot={editingShot}
            onChange={(patch) => updateShot(editingIndex, patch)}
          />
        </div>
      )}
    </div>
  );
}

function ShotEditor({
  shot,
  onChange,
}: {
  shot: ResolvedShot;
  onChange: (patch: Partial<ResolvedShot>) => void;
}) {
  const rubricText = shot.rubric_plan ? JSON.stringify(shot.rubric_plan, null, 2) : "";
  const onRubricChange = (value: string) => {
    try {
      onChange({ rubric_plan: value.trim() ? JSON.parse(value) : null });
    } catch {
      onChange({ rubric_plan: { RAW_USER_RUBRIC_EDIT: value } });
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Motion">
          <select
            value={shot.motion}
            onChange={(event) => onChange({ motion: event.target.value })}
            className="h-9 w-full rounded-xl border border-border bg-white px-3 text-xs text-ink"
          >
            {MOTIONS.map((motion) => <option key={motion} value={motion}>{motion}</option>)}
          </select>
        </Field>
      </div>

      <Field label="Scene Purpose">
        <Textarea
          value={shot.scene_purpose ?? ""}
          onChange={(event) => onChange({ scene_purpose: event.target.value })}
          className="min-h-[70px] text-xs"
        />
      </Field>
      <Field label="Style Notes">
        <Textarea
          value={shot.style_notes ?? ""}
          onChange={(event) => onChange({ style_notes: event.target.value })}
          className="min-h-[96px] text-xs"
        />
      </Field>
      <div className="grid gap-3 lg:grid-cols-2">
        <Field label="Beat Plan">
          <Textarea
            value={shot.beat_plan ?? ""}
            onChange={(event) => onChange({ beat_plan: event.target.value })}
            className="min-h-[86px] text-xs"
          />
        </Field>
        <Field label="Masking Plan">
          <Textarea
            value={shot.masking_plan ?? ""}
            onChange={(event) => onChange({ masking_plan: event.target.value })}
            className="min-h-[86px] text-xs"
          />
        </Field>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Field label="Transition Plan">
          <Textarea
            value={shot.transition_plan ?? ""}
            onChange={(event) => onChange({ transition_plan: event.target.value })}
            className="min-h-[86px] text-xs"
          />
        </Field>
        <Field label="Continuity Notes">
          <Textarea
            value={shot.continuity_notes ?? ""}
            onChange={(event) => onChange({ continuity_notes: event.target.value })}
            className="min-h-[86px] text-xs"
          />
        </Field>
      </div>
      <Field label="FAL Prompt / AI Draft">
        <Textarea
          value={shot.style_recipe_prompt ?? ""}
          onChange={(event) => onChange({ style_recipe_prompt: event.target.value })}
          className="min-h-[150px] font-mono text-[11px]"
        />
      </Field>
      <Field label="Rubric JSON">
        <Textarea
          defaultValue={rubricText}
          onBlur={(event) => onRubricChange(event.target.value)}
          className="min-h-[160px] font-mono text-[11px]"
        />
      </Field>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-ink-muted">{label}</Label>
      {children}
    </div>
  );
}

function shortText(value: string, limit: number) {
  return value.length > limit ? `${value.slice(0, limit - 1)}...` : value;
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
  icon?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-white p-3",
        warning ? "border-amber-200 bg-amber-50" : "border-border/60",
      )}
    >
      <div className="flex items-center gap-1 text-xs text-ink-muted">
        {icon}
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 font-display text-xl font-semibold",
          accent && "gradient-text",
          warning && "text-amber-700",
        )}
      >
        {value}
      </div>
    </div>
  );
}
