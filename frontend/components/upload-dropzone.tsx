"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload as UploadIcon, X, ImageIcon } from "lucide-react";

import { api, type Upload } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn, formatBytes } from "@/lib/utils";

interface Props {
  projectId: string;
  uploads: Upload[];
  onChange: (uploads: Upload[]) => void;
}

export function UploadDropzone({ projectId, uploads, onChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"] },
    multiple: true,
    onDrop: async (files) => {
      if (!files.length) return;
      setBusy(true);
      setProgress(0);
      try {
        // Chunk uploads to ~10 at a time so we can show progress
        const chunkSize = 10;
        const all: Upload[] = [...uploads];
        for (let i = 0; i < files.length; i += chunkSize) {
          const chunk = files.slice(i, i + chunkSize);
          const result = await api.uploadImages(projectId, chunk);
          all.push(...result);
          setProgress(Math.min(1, (i + chunk.length) / files.length));
        }
        // Dedup by id
        const seen = new Set<string>();
        onChange(all.filter((u) => (seen.has(u.id) ? false : (seen.add(u.id), true))));
      } catch (e) {
        alert(`Upload failed: ${e instanceof Error ? e.message : e}`);
      } finally {
        setBusy(false);
      }
    },
  });

  const onRemove = async (id: string) => {
    if (!confirm("Remove this image?")) return;
    await api.deleteUpload(projectId, id);
    onChange(uploads.filter((u) => u.id !== id));
  };

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "relative rounded-2xl border-2 border-dashed p-10 text-center transition-all cursor-pointer",
          isDragActive
            ? "border-accent bg-accent-50"
            : "border-border-strong bg-gradient-soft hover:border-primary-300 hover:bg-primary-50/50",
        )}
      >
        <input {...getInputProps()} />
        <div className="w-14 h-14 mx-auto rounded-2xl bg-white flex items-center justify-center shadow-card mb-4">
          <UploadIcon className="w-6 h-6 text-primary" />
        </div>
        <p className="font-display text-lg font-semibold">
          {isDragActive ? "Drop them here" : "Drop 50–150 property photos"}
        </p>
        <p className="text-sm text-ink-muted mt-1">
          JPG, PNG, WebP, HEIC. We'll analyze and storyboard them automatically.
        </p>
        {busy && (
          <div className="mt-5 max-w-sm mx-auto">
            <div className="h-1.5 rounded-full bg-white overflow-hidden">
              <div
                className="h-full bg-gradient-brand transition-all"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <p className="text-xs text-ink-muted mt-2">
              Uploading… {Math.round(progress * 100)}%
            </p>
          </div>
        )}
      </div>

      {uploads.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-ink-muted">
              <ImageIcon className="inline w-4 h-4 mr-1.5 align-text-bottom" />
              {uploads.length} {uploads.length === 1 ? "image" : "images"} uploaded
            </p>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
            {uploads.map((u) => (
              <div
                key={u.id}
                className="group relative aspect-square rounded-lg overflow-hidden bg-primary-50 border border-border/40"
              >
                <img
                  src={api.uploadFileUrl(u.id)}
                  alt={u.filename}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                <button
                  onClick={() => onRemove(u.id)}
                  className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center hover:bg-red-500"
                  aria-label="Remove"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
