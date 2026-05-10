"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Check, Loader2, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RenderProgressCard } from "@/components/render-progress";
import { StoryboardTimeline } from "@/components/storyboard-timeline";
import { TemplateCard } from "@/components/template-card";
import { UploadDropzone } from "@/components/upload-dropzone";
import {
  api,
  type Project,
  type RenderJob,
  type Storyboard,
  type Template,
  type Upload,
} from "@/lib/api";
import { connectProgressWS, type ProgressMessage } from "@/lib/ws";
import { cn } from "@/lib/utils";

type Step = "upload" | "template" | "storyboard" | "render";

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const [project, setProject] = useState<Project | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [renders, setRenders] = useState<RenderJob[]>([]);
  const [step, setStep] = useState<Step>("upload");

  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [generatingStoryboard, setGeneratingStoryboard] = useState(false);

  const [liveProgress, setLiveProgress] = useState<Record<string, number>>({});

  // Initial load
  useEffect(() => {
    Promise.all([
      api.getProject(projectId),
      api.listUploads(projectId),
      api.listTemplates(),
      api.getStoryboard(projectId),
      api.listRenders(projectId),
    ]).then(([p, u, t, s, r]) => {
      setProject(p);
      setUploads(u);
      setTemplates(t);
      if (s) setStoryboard(s);
      setRenders(r);
      setSelectedTemplate(p.template_id ?? null);
      // pick the most advanced step
      if (r.length) setStep("render");
      else if (s) setStep("storyboard");
      else if (p.template_id) setStep("template");
      else if (u.length) setStep("template");
    });
  }, [projectId]);

  // WebSocket: live render progress
  useEffect(() => {
    const close = connectProgressWS(projectId, (msg: ProgressMessage) => {
      if (msg.progress != null) {
        setLiveProgress((prev) => ({ ...prev, [msg.render_id]: msg.progress! }));
      }
      if (msg.status === "succeeded" || msg.status === "failed") {
        api.listRenders(projectId).then(setRenders);
      }
    });
    return close;
  }, [projectId]);

  const onGenerateStoryboard = async () => {
    if (!selectedTemplate) return;
    setGeneratingStoryboard(true);
    try {
      const sb = await api.generateStoryboard(projectId, selectedTemplate);
      setStoryboard(sb);
      setStep("storyboard");
    } catch (e) {
      const savedStoryboard = await api.getStoryboard(projectId).catch(() => null);
      if (savedStoryboard) {
        setStoryboard(savedStoryboard);
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
      const job = await api.startRender(projectId, passType);
      setRenders((rs) => [job, ...rs]);
      setStep("render");
    } catch (e) {
      alert(`Render failed to start: ${e instanceof Error ? e.message : e}`);
    }
  };

  if (!project) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  const stepIdx = (["upload", "template", "storyboard", "render"] as Step[]).indexOf(step);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 space-y-8">
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
      <Stepper step={step} onSelect={setStep} stepIdx={stepIdx} hasUploads={uploads.length > 0} hasTemplate={!!selectedTemplate} hasStoryboard={!!storyboard} />

      {/* Step content */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload property photos</CardTitle>
          </CardHeader>
          <CardContent>
            <UploadDropzone
              projectId={projectId}
              uploads={uploads}
              onChange={setUploads}
            />
          </CardContent>
          <div className="flex justify-end p-6 border-t border-white/[0.06]">
            <Button
              onClick={() => setStep("template")}
              disabled={uploads.length === 0}
            >
              Continue <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>
      )}

      {step === "template" && (
        <Card>
          <CardHeader>
            <CardTitle>Pick a template</CardTitle>
            <CardDescription>
              Each template is a parameterized storyboard authored by a pro video editor.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {templates.length === 0 ? (
              <div className="skeleton h-40" />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {templates.map((t) => (
                  <TemplateCard
                    key={t.template_id}
                    template={t}
                    selected={selectedTemplate === t.template_id}
                    onSelect={() => setSelectedTemplate(t.template_id)}
                  />
                ))}
              </div>
            )}
          </CardContent>
          <div className="flex justify-between gap-3 p-6 border-t border-white/[0.06]">
            <Button variant="ghost" onClick={() => setStep("upload")}>
              ← Back
            </Button>
            <Button
              onClick={onGenerateStoryboard}
              disabled={!selectedTemplate || generatingStoryboard}
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
                Auto-assigned shots, ready to render. Run a draft preview first to validate timing.
              </CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={onGenerateStoryboard}
              disabled={generatingStoryboard}
            >
              {generatingStoryboard ? "…" : "Regenerate"}
            </Button>
          </CardHeader>
          <CardContent>
            <StoryboardTimeline storyboard={storyboard} uploads={uploads} />
          </CardContent>
          <div className="flex justify-between gap-3 p-6 border-t border-white/[0.06]">
            <Button variant="ghost" onClick={() => setStep("template")}>
              ← Change template
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onRender("draft")}>
                <Sparkles className="w-4 h-4" /> Render draft
              </Button>
              <Button onClick={() => onRender("final")}>
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

function Stepper({
  step,
  onSelect,
  stepIdx,
  hasUploads,
  hasTemplate,
  hasStoryboard,
}: {
  step: Step;
  onSelect: (s: Step) => void;
  stepIdx: number;
  hasUploads: boolean;
  hasTemplate: boolean;
  hasStoryboard: boolean;
}) {
  const items: { step: Step; label: string; done: boolean }[] = [
    { step: "upload", label: "Upload", done: hasUploads },
    { step: "template", label: "Template", done: hasTemplate },
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
          (i === 2 && hasTemplate) ||
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
                  ? "border-white/[0.08] bg-[#14141f] hover:border-primary-400/30"
                  : "border-white/[0.04] bg-[#14141f]/40 opacity-50 cursor-not-allowed",
            )}
          >
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold",
                  it.done
                    ? "bg-emerald-900/40 text-emerald-400"
                    : isCurrent
                      ? "bg-gradient-brand text-white"
                      : "bg-primary-200/20 text-primary-700",
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
