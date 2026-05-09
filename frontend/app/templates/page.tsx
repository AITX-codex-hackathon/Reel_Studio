"use client";

import { useEffect, useState } from "react";
import { Loader2, Sparkles, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { TemplateCard } from "@/components/template-card";
import { StyleCard } from "@/components/style-card";
import { api, type Template, type VideoStyle } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selected, setSelected] = useState<Template | null>(null);

  const [styles, setStyles] = useState<VideoStyle[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [selectedStyle, setSelectedStyle] = useState<VideoStyle | null>(null);

  const [brief, setBrief] = useState("");
  const [name, setName] = useState("");
  const [save, setSave] = useState(true);
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    api.listTemplates().then(setTemplates);
    api.listStyles().then(setStyles);
    api.listStyleCategories().then((cats) => setCategories(["All", ...cats]));
  }, []);

  const filteredStyles =
    activeCategory === "All"
      ? styles
      : styles.filter((s) => s.category === activeCategory);

  const onTranslate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim()) return;
    setTranslating(true);
    try {
      const t = await api.templateFromPrompt(brief, name || undefined, save);
      setSelected(t);
      if (save) {
        const list = await api.listTemplates();
        setTemplates(list);
      }
    } catch (err) {
      alert(`Translation failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setTranslating(false);
    }
  };

  return (
    <div className="space-y-12">
      <div>
        <h1 className="font-display text-3xl font-bold">Templates</h1>
        <p className="text-ink-muted mt-1">
          Reusable storyboards and cinematic shot styles. Pick one to start a project.
        </p>
      </div>

      {/* ── Bundled storyboard templates ── */}
      <section>
        <h2 className="font-display text-xl font-semibold mb-4">Bundled</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <TemplateCard
              key={t.template_id}
              template={t}
              selected={selected?.template_id === t.template_id}
              onSelect={() => { setSelected(t); setSelectedStyle(null); }}
            />
          ))}
        </div>
      </section>

      {/* ── Style Library ── */}
      <section>
        <div className="flex items-end justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="font-display text-xl font-semibold">Style Library</h2>
            <p className="text-sm text-ink-muted mt-0.5">
              {styles.length} cinematic shot styles — choose one to drive i2v generation.
            </p>
          </div>
          <Badge variant="muted">{filteredStyles.length} shown</Badge>
        </div>

        {/* Category filter chips */}
        <div className="flex flex-wrap gap-2 mb-5">
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                activeCategory === cat
                  ? "bg-primary text-white border-primary shadow-brand-soft"
                  : "bg-white text-ink-muted border-border/60 hover:border-primary/40 hover:text-primary",
              )}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Style cards grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filteredStyles.map((s) => (
            <StyleCard
              key={s.style_id}
              style={s}
              selected={selectedStyle?.style_id === s.style_id}
              onSelect={() => { setSelectedStyle(s); setSelected(null); }}
            />
          ))}
        </div>
      </section>

      {/* ── Author from prompt ── */}
      <section>
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-accent" />
              <CardTitle>Create a template from a brief</CardTitle>
            </div>
            <CardDescription>
              Describe the reel in plain English. The AI turns it into a structured YAML template
              you can reuse across projects.
            </CardDescription>
          </CardHeader>
          <form onSubmit={onTranslate}>
            <CardContent className="space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="name">Template name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Loft Walkthrough — 45s"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="brief">Brief</Label>
                <Textarea
                  id="brief"
                  rows={8}
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  placeholder={
                    "45-second reel for a downtown loft. Open with a 4-second slow zoom on the exterior, golden hour. " +
                    "Cut to the foyer at 4s with a push-in. Music starts at 4s, ambient slow. Show kitchen highlights " +
                    "between 8 and 16s with two detail beats. End on a sunset rooftop view with the price overlaid."
                  }
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={save}
                  onChange={(e) => setSave(e.target.checked)}
                />
                Save to template library after generating
              </label>
            </CardContent>
            <div className="flex justify-end gap-3 p-6 border-t border-border/40">
              <Button type="submit" disabled={!brief.trim() || translating}>
                {translating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Translating…
                  </>
                ) : (
                  <>
                    <Wand2 className="w-4 h-4" /> Translate to YAML
                  </>
                )}
              </Button>
            </div>
          </form>
        </Card>
      </section>

      {/* ── Template inspector ── */}
      {selected && (
        <section>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div>
                  <CardTitle>{selected.name}</CardTitle>
                  <CardDescription>{selected.description}</CardDescription>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Badge variant="default">{selected.aspect_ratio}</Badge>
                  <Badge variant="muted">{selected.target_duration_sec}s</Badge>
                  <Badge variant="muted">{selected.shot_slots.length} shots</Badge>
                  <Badge variant="muted">{selected.pacing_mode}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <h3 className="text-sm font-semibold text-ink-muted mb-2 uppercase tracking-wider">
                Shot slots
              </h3>
              <div className="space-y-2">
                {selected.shot_slots.map((slot, i) => (
                  <div
                    key={slot.slot_id}
                    className="flex gap-3 p-3 rounded-xl border border-border/60 bg-white"
                  >
                    <div className="w-8 text-center font-display text-ink-subtle">{i + 1}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm">{slot.slot_id}</span>
                        {slot.room_type && <Badge variant="muted">{slot.room_type}</Badge>}
                        <Badge variant="outline">{slot.motion}</Badge>
                        {!slot.must_fill && <Badge variant="muted">optional</Badge>}
                        {slot.fallback_to_generated && (
                          <Badge variant="accent">
                            <Wand2 className="w-2.5 h-2.5" /> may generate
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-ink-muted mt-1">{slot.description}</p>
                      <div className="text-xs text-ink-subtle mt-1">
                        {slot.duration_sec.toFixed(1)}s · transition: {slot.transition_in}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {/* ── Style inspector ── */}
      {selectedStyle && (
        <section>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div>
                  <CardTitle>{selectedStyle.camera_motion}</CardTitle>
                  <CardDescription>
                    {selectedStyle.style_id} · {selectedStyle.category} · {selectedStyle.mood}
                  </CardDescription>
                </div>
                <Badge variant="accent">{selectedStyle.environmental_dynamics}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <h3 className="text-sm font-semibold text-ink-muted mb-2 uppercase tracking-wider">
                Video prompt
              </h3>
              <p className="text-sm text-ink leading-relaxed bg-surface-alt rounded-xl p-4 border border-border/40">
                {selectedStyle.video_prompt}
              </p>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
