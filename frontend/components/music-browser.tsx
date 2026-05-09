"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Check, Loader2, Music2, Pause, Play, Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { api, type FreeMusicTrack, type MusicInsertJob, type ProjectMusic } from "@/lib/api";
import { cn } from "@/lib/utils";

type MusicBrowserProps = {
  projectId: string;
  currentMusic: ProjectMusic | null;
  onInserted: (music: ProjectMusic) => void;
};

export function MusicBrowser({ projectId, currentMusic, onInserted }: MusicBrowserProps) {
  const [query, setQuery] = useState("");
  const [tracks, setTracks] = useState<FreeMusicTrack[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<FreeMusicTrack | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<MusicInsertJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const activeTrackId = currentMusic?.track_id ?? selectedTrack?.id ?? null;
  const inserting = job?.status === "queued" || job?.status === "running";

  const progressText = useMemo(() => {
    if (!job) return "";
    if (job.status === "complete") return "Ready";
    if (job.status === "failed") return "Failed";
    return job.message || "Preparing music";
  }, [job]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialTracks() {
      setLoading(true);
      setError(null);
      try {
        const results = await api.listFreeMusicTracks("", 20);
        if (cancelled) return;
        setTracks(results);
        if (results.length > 0) {
          setSelectedTrack(results[0]);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadInitialTracks();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!job || job.status === "complete" || job.status === "failed") return;

    const timer = window.setInterval(async () => {
      try {
        const next = await api.getMusicInsertJob(projectId, job.job_id);
        setJob(next);
        if (next.status === "complete" && next.result) {
          onInserted(next.result);
        }
        if (next.status === "failed") {
          setError(next.error || "Music insert failed");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [job, onInserted, projectId]);

  const loadTracks = async (nextQuery = query) => {
    setLoading(true);
    setError(null);
    try {
      const results = await api.listFreeMusicTracks(nextQuery, 20);
      setTracks(results);
      if (!selectedTrack && results.length > 0) {
        setSelectedTrack(results[0]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadTracks(query);
  };

  const togglePreview = async (track: FreeMusicTrack) => {
    if (!track.preview_url) return;
    if (!audioRef.current) {
      audioRef.current = new Audio();
      audioRef.current.addEventListener("ended", () => setPlayingId(null));
    }

    if (playingId === track.id) {
      audioRef.current.pause();
      setPlayingId(null);
      return;
    }

    audioRef.current.pause();
    audioRef.current.src = track.preview_url;
    try {
      await audioRef.current.play();
      setPlayingId(track.id);
    } catch {
      setError("Preview playback was blocked by the browser.");
    }
  };

  const insertSelected = async () => {
    if (!selectedTrack) return;
    setError(null);
    setJob(null);
    try {
      const nextJob = await api.insertMusic(projectId, selectedTrack.id);
      setJob(nextJob);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <form onSubmit={onSearch} className="flex min-w-0 flex-1 gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search cinematic, commercial, piano"
              className="pl-9"
            />
          </div>
          <Button type="submit" variant="outline" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Search
          </Button>
        </form>

        <Button onClick={insertSelected} disabled={!selectedTrack || inserting}>
          {inserting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Insert
        </Button>
      </div>

      {currentMusic && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <div className="flex flex-wrap items-center gap-2">
            <Check className="h-4 w-4" />
            <span className="font-medium">
              {currentMusic.artist} - {currentMusic.title}
            </span>
            <Badge variant="success">{currentMusic.beat_count} beats</Badge>
            {currentMusic.tempo && <Badge variant="outline">{Math.round(currentMusic.tempo)} BPM</Badge>}
          </div>
        </div>
      )}

      {job && (
        <div className="rounded-lg border border-border bg-white px-4 py-3">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium text-ink">{progressText}</span>
            <span className="text-ink-muted">{Math.round(job.progress * 100)}%</span>
          </div>
          <Progress value={job.progress * 100} />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="max-h-[440px] overflow-y-auto rounded-lg border border-border">
        {loading && tracks.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-ink-muted">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading tracks
          </div>
        ) : tracks.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-ink-muted">
            No suitable tracks found.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {tracks.map((track) => {
              const selected = selectedTrack?.id === track.id || activeTrackId === track.id;
              const playing = playingId === track.id;

              return (
                <div
                  key={track.id}
                  onClick={() => setSelectedTrack(track)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedTrack(track);
                    }
                  }}
                  className={cn(
                    "grid w-full cursor-pointer grid-cols-[56px_1fr_auto] items-center gap-3 px-4 py-3 text-left transition-colors",
                    selected ? "bg-primary-50" : "bg-white hover:bg-primary-50/60",
                  )}
                >
                  <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-md bg-primary-100">
                    {track.thumbnail_url ? (
                      <img
                        src={track.thumbnail_url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <Music2 className="h-5 w-5 text-primary-700" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="truncate font-medium text-ink">{track.title}</span>
                      {selected && <Badge variant="default">Selected</Badge>}
                    </div>
                    <div className="mt-0.5 truncate text-sm text-ink-muted">{track.artist}</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {formatDuration(track.duration_sec) && (
                        <Badge variant="outline">{formatDuration(track.duration_sec)}</Badge>
                      )}
                      {track.genre && <Badge variant="muted">{track.genre}</Badge>}
                      {track.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="muted">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    disabled={!track.preview_url}
                    onClick={(event) => {
                      event.stopPropagation();
                      togglePreview(track);
                    }}
                    aria-label={playing ? "Pause preview" : "Play preview"}
                  >
                    {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function formatDuration(value?: number | null) {
  if (!value) return "";
  const total = Math.round(value);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
