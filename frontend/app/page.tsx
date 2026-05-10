"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { ArrowRight, Film, Plus, Sparkles, Wand2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Project } from "@/lib/api";
import { NewReelButton } from "@/components/auth/NewReelButton";

const SHOWCASE_IMAGES = [
  "/demo/living-room.jpg",
  "/demo/open-kitchen.jpg",
  "/demo/window-view.jpg",
  "/demo/kitchen.jpg",
  "/demo/hallway.jpg",
];

const KENBURNS_EFFECTS = [
  "animate-kb-zoom-in",
  "animate-kb-slide-left",
  "animate-kb-zoom-out",
  "animate-kb-slide-right",
];

function HeroBackground() {
  const [current, setCurrent] = useState(0);
  const [prev, setPrev] = useState(-1);

  useEffect(() => {
    const timer = setInterval(() => {
      setPrev(current);
      setCurrent((c) => (c + 1) % SHOWCASE_IMAGES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [current]);

  return (
    <div className="absolute inset-0 overflow-hidden">
      {SHOWCASE_IMAGES.map((src, i) => {
        const isActive = i === current;
        const isPrev = i === prev;
        return (
          <div
            key={src}
            className={`absolute inset-0 transition-opacity duration-[1200ms] ease-in-out ${
              isActive ? "opacity-100 z-[2]" : isPrev ? "opacity-0 z-[1]" : "opacity-0 z-0"
            }`}
          >
            <Image
              src={src}
              alt=""
              fill
              className={`object-cover ${isActive ? KENBURNS_EFFECTS[i % KENBURNS_EFFECTS.length] : ""}`}
              priority={i === 0}
              sizes="100vw"
              quality={90}
            />
          </div>
        );
      })}
      <div className="absolute inset-0 z-[3]" style={{
        background: "linear-gradient(to right, #0a0a0f 0%, rgba(10,10,15,0.92) 20%, rgba(10,10,15,0.5) 45%, rgba(10,10,15,0.1) 65%, transparent 80%)"
      }} />
      <div className="absolute inset-0 z-[3] bg-gradient-to-t from-[#0a0a0f]/80 via-transparent to-[#0a0a0f]/20" />
    </div>
  );
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Hero — full-width CapCut style */}
      <section className="relative w-full overflow-hidden" style={{ height: "520px" }}>
        <HeroBackground />

        <div className="relative z-10 h-full mx-auto max-w-7xl px-6 flex items-center">
          <div className="max-w-xl space-y-5">
            <h1 className="font-display text-4xl md:text-5xl lg:text-[52px] font-bold leading-[1.1] tracking-tight text-white">
              Turn property photos into{" "}
              <span className="gradient-text">cinematic reels</span>
            </h1>
            <p className="text-base text-white/50 leading-relaxed max-w-md">
              Upload your property photos, pick a template, and our AI agents
              storyboard, fill missing shots, and render a beat-aware 60-second
              reel — ready for Instagram and TikTok.
            </p>

            <div className="flex flex-wrap gap-3 pt-1">
              <NewReelButton size="lg">
                <Plus className="w-4 h-4" />
                Start a new reel
              </NewReelButton>
              <Button asChild variant="outline" size="lg">
                <Link href="/templates">
                  Browse templates <ArrowRight className="w-4 h-4" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-6 space-y-16 mt-12 pb-10">
        {/* Projects */}
        <section>
          <div className="flex items-end justify-between mb-6">
            <div>
              <h2 className="font-display text-2xl font-semibold text-white">Your projects</h2>
              <p className="text-sm text-ink-muted mt-1">
                Continue where you left off, or start fresh.
              </p>
            </div>
            <NewReelButton size="sm">
              <Plus className="w-4 h-4" /> New
            </NewReelButton>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="skeleton h-64 rounded-2xl" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <Card>
              <CardContent className="p-12 text-center">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-gradient-soft flex items-center justify-center mb-4">
                  <Film className="w-7 h-7 text-primary-400" />
                </div>
                <h3 className="font-display text-lg font-semibold text-white">No projects yet</h3>
                <p className="text-sm text-ink-muted mt-1 mb-6">
                  Create your first reel — the whole flow takes about 2 minutes.
                </p>
                <NewReelButton>
                  <Wand2 className="w-4 h-4" /> Create your first reel
                </NewReelButton>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {projects.map((p, i) => (
                <Link key={p.id} href={`/projects/${p.id}`} className="group">
                  <Card className="overflow-hidden hover:shadow-brand-soft hover:-translate-y-1 transition-all duration-300">
                    <div className="aspect-video relative overflow-hidden">
                      <Image
                        src={SHOWCASE_IMAGES[i % SHOWCASE_IMAGES.length]}
                        alt={p.name}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-500"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-[#14141f] via-transparent to-transparent" />
                      <div className="absolute bottom-3 left-3">
                        <div className="flex flex-wrap gap-1.5">
                          {p.template_id && <Badge variant="default">{p.template_id}</Badge>}
                          {p.storyboard_id ? (
                            <Badge variant="success">storyboard ready</Badge>
                          ) : (
                            <Badge variant="muted">draft</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <CardHeader className="pb-2">
                      <CardTitle className="line-clamp-1 group-hover:text-accent-400 transition-colors text-white">
                        {p.name}
                      </CardTitle>
                      <CardDescription className="line-clamp-1 text-ink-muted">
                        {p.address || "No address yet"}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
