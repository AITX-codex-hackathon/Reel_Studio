"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function NewProjectPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "",
    address: "",
    price: "",
    beds: "",
    baths: "",
    sqft: "",
    description: "",
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const project = await api.createProject({
        name: form.name,
        address: form.address || undefined,
        price: form.price || undefined,
        beds: form.beds ? Number(form.beds) : undefined,
        baths: form.baths ? Number(form.baths) : undefined,
        sqft: form.sqft ? Number(form.sqft) : undefined,
        description: form.description || undefined,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      alert(`Failed: ${err instanceof Error ? err.message : err}`);
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 text-xs text-primary font-medium mb-2">
          <Sparkles className="w-3.5 h-3.5" /> Step 1 of 4
        </div>
        <h1 className="font-display text-3xl font-bold">Create a new project</h1>
        <p className="text-ink-muted mt-2">
          Property details so the AI can write smart text overlays.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Property details</CardTitle>
          <CardDescription>
            Only the name is required. The rest gets used in text overlays and AI prompts.
          </CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="space-y-5">
            <Field label="Project name *" htmlFor="name">
              <Input
                id="name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="123 Cherry Lane Listing"
              />
            </Field>

            <Field label="Address" htmlFor="address">
              <Input
                id="address"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="123 Cherry Lane, Austin TX"
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Price" htmlFor="price">
                <Input
                  id="price"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: e.target.value })}
                  placeholder="$1,250,000"
                />
              </Field>
              <Field label="Square feet" htmlFor="sqft">
                <Input
                  id="sqft"
                  type="number"
                  value={form.sqft}
                  onChange={(e) => setForm({ ...form, sqft: e.target.value })}
                  placeholder="3200"
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Beds" htmlFor="beds">
                <Input
                  id="beds"
                  type="number"
                  value={form.beds}
                  onChange={(e) => setForm({ ...form, beds: e.target.value })}
                  placeholder="4"
                />
              </Field>
              <Field label="Baths" htmlFor="baths">
                <Input
                  id="baths"
                  type="number"
                  step="0.5"
                  value={form.baths}
                  onChange={(e) => setForm({ ...form, baths: e.target.value })}
                  placeholder="3.5"
                />
              </Field>
            </div>

            <Field label="Description" htmlFor="description">
              <Textarea
                id="description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Newly renovated craftsman with a chef's kitchen and resort-style backyard..."
              />
            </Field>
          </CardContent>
          <div className="flex justify-end gap-3 p-6 border-t border-white/[0.06]">
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.back()}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !form.name}>
              {submitting ? "Creating…" : "Continue"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}
