"use client";

import { useState, type ReactNode } from "react";
import { Sparkles, AlertTriangle, Wand2, Clapperboard, Pencil, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
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
  onSave?: () => void;
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

const TRANSITIONS = ["cut", "dissolve", "slide_left", "slide_right", "whip_pan", "fade"];

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
  const uploadById = new Map(uploads.map((u) => [u.id, u]));

  const updateShot = (index: number, patch: Partial<ResolvedShot>) => {
    if (!onChange) return;
    const shots = storyboard.shots.map((shot, shotIndex) => (
      shotIndex === index ? { ...shot, ...patch } : shot
    ));
    onChange({ ...storyboard, shots });
  };

  return (
    <div className="space-y-6">
      {editable && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-100 bg-primary-50/40 p-3">
          <p className="text-sm text-ink-muted">
            Edit any scene before render: prompt, style notes, camera motion, transition, beat plan, or mask plan.
          </p>
          <Button size="sm" onClick={onSave} disabled={!dirty || saving}>
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving…" : dirty ? "Save edits" : "Saved"}
          </Button>
        </div>
      )}

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

      {storyboard.selected_upload_ids && storyboard.selected_upload_ids.length > 0 && uploads.length > 20 && (
        <p className="text-sm text-ink-muted">
          AI curated {storyboard.selected_upload_ids.length} of {uploads.length} uploaded photos for this story.
          {storyboard.photo_selection_notes ? ` ${storyboard.photo_selection_notes}` : ""}
        </p>
      )}

      {storyboard.creative_brief && (
        <div className="rounded-xl border border-border/60 bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-ink">
            <Clapperboard className="w-4 h-4 text-primary" />
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
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 flex gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-amber-900">
              {storyboard.unfilled_slot_ids.length} slot
              {storyboard.unfilled_slot_ids.length === 1 ? "" : "s"} couldn't be filled
            </p>
            <p className="text-amber-800/80 mt-0.5">
              Either upload more matching photos or enable FAL generation
              (set <code className="bg-amber-100 px-1 rounded">FAL_API_KEY</code>).
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
                  {editable && (
                    <button
                      type="button"
                      onClick={() => setEditingShotId(editingShotId === shot.slot_id ? null : shot.slot_id)}
                      className="inline-flex h-6 items-center gap-1 rounded-full border border-border/70 px-2 text-[10px] font-medium text-ink-muted hover:border-primary-300 hover:text-primary"
                    >
                      <Pencil className="w-3 h-3" />
                      {editingShotId === shot.slot_id ? "Close" : "Edit"}
                    </button>
                  )}
                </div>
                <div className="text-xs text-ink-subtle mt-1">
                  {formatSeconds(shot.start_time_sec)} → {formatSeconds(shot.start_time_sec + shot.duration_sec)} · {shot.duration_sec.toFixed(1)}s · {shot.transition_in}
                </div>
                {shot.scene_purpose && (
                  <p className="mt-2 text-xs text-ink-muted">{shortText(shot.scene_purpose, 260)}</p>
                )}
                {(shot.masking_plan || shot.beat_plan) && (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-ink-subtle">
                    {shot.beat_plan && <Badge variant="muted">beat: {shortText(shot.beat_plan, 74)}</Badge>}
                    {shot.masking_plan && <Badge variant="muted">mask: {shortText(shot.masking_plan, 74)}</Badge>}
                    {shot.rubric_plan && <Badge variant="muted">rubric</Badge>}
                  </div>
                )}
                {editable && editingShotId === shot.slot_id && (
                  <ShotEditor
                    shot={shot}
                    onChange={(patch) => updateShot(i, patch)}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
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
    <div className="mt-3 space-y-3 rounded-xl border border-border/60 bg-surface-alt/50 p-3">
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
        <Field label="Transition">
          <select
            value={shot.transition_in}
            onChange={(event) => onChange({ transition_in: event.target.value })}
            className="h-9 w-full rounded-xl border border-border bg-white px-3 text-xs text-ink"
          >
            {TRANSITIONS.map((transition) => <option key={transition} value={transition}>{transition}</option>)}
          </select>
        </Field>
        <Field label="Strength">
          <Input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={shot.motion_strength}
            onChange={(event) => onChange({ motion_strength: Number(event.target.value) })}
            className="h-9 text-xs"
          />
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
      <Field label="FAL Prompt Override">
        <Textarea
          value={shot.style_recipe_prompt ?? ""}
          onChange={(event) => onChange({ style_recipe_prompt: event.target.value })}
          className="min-h-[130px] font-mono text-[11px]"
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
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
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
