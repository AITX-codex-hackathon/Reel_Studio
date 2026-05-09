"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Film, Plus, Sparkles, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Health, type Project } from "@/lib/api";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listProjects(), api.health()])
      .then(([p, h]) => {
        setProjects(p);
        setHealth(h);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-soft border border-border/40 p-10">
        <div className="relative z-10 max-w-2xl">
          <Badge variant="accent" className="mb-4">
            <Sparkles className="w-3 h-3" /> AI Reel Studio
          </Badge>
          <h1 className="font-display text-4xl md:text-5xl font-bold leading-tight tracking-tight">
            Turn property photos into <span className="gradient-text">cinematic reels</span> in minutes.
          </h1>
          <p className="mt-4 text-lg text-ink-muted leading-relaxed">
            Upload 50–150 photos, pick a template, and our AI agents storyboard, fill missing
            shots with Nano Banana, and render a beat-aware 60-second reel.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/projects/new">
                <Plus className="w-4 h-4" />
                Start a new reel
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/templates">
                Browse templates <ArrowRight className="w-4 h-4" />
              </Link>
            </Button>
          </div>
        </div>
        <div className="pointer-events-none absolute -right-16 -top-16 w-80 h-80 rounded-full bg-accent/20 blur-3xl" />
        <div className="pointer-events-none absolute -right-8 -bottom-32 w-96 h-96 rounded-full bg-primary-300/30 blur-3xl" />
      </section>

      {/* Provider status */}
      {health && (
        <section className="flex flex-wrap gap-2">
          {Object.entries(health.providers).map(([name, on]) => (
            <Badge key={name} variant={on ? "success" : "muted"}>
              <span className={`w-1.5 h-1.5 rounded-full ${on ? "bg-emerald-500" : "bg-ink-subtle/50"}`} />
              {name}
              <span className="text-ink-subtle">{on ? "ready" : "no key"}</span>
            </Badge>
          ))}
        </section>
      )}

      {/* Projects */}
      <section>
        <div className="flex items-end justify-between mb-6">
          <div>
            <h2 className="font-display text-2xl font-semibold">Your projects</h2>
            <p className="text-sm text-ink-muted mt-1">
              Continue where you left off, or start fresh.
            </p>
          </div>
          <Button asChild size="sm">
            <Link href="/projects/new">
              <Plus className="w-4 h-4" /> New
            </Link>
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="skeleton h-52" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-gradient-soft flex items-center justify-center mb-4">
                <Film className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-display text-lg font-semibold">No projects yet</h3>
              <p className="text-sm text-ink-muted mt-1 mb-6">
                Create your first reel — the whole flow takes about 2 minutes.
              </p>
              <Button asChild>
                <Link href="/projects/new">
                  <Wand2 className="w-4 h-4" /> Create your first reel
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="group">
                <Card className="hover:shadow-brand-soft hover:-translate-y-0.5 transition-all">
                  <div className="aspect-video bg-gradient-soft border-b border-border/40 flex items-center justify-center">
                    <Film className="w-10 h-10 text-primary/40" />
                  </div>
                  <CardHeader>
                    <CardTitle className="line-clamp-1 group-hover:text-primary transition-colors">
                      {p.name}
                    </CardTitle>
                    <CardDescription className="line-clamp-1">
                      {p.address || "No address yet"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-1.5">
                      {p.template_id && <Badge variant="default">{p.template_id}</Badge>}
                      {p.storyboard_id ? (
                        <Badge variant="success">storyboard ready</Badge>
                      ) : (
                        <Badge variant="muted">draft</Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
