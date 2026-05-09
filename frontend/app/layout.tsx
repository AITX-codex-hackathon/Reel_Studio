import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Realstate — AI Reels for Real Estate",
  description: "Turn 50–150 property photos into a cinematic 1-minute reel. Powered by AI.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`}>
      <body className="min-h-screen font-sans">
        <header className="sticky top-0 z-40 glass border-b border-border/40">
          <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-brand flex items-center justify-center shadow-brand-soft group-hover:scale-105 transition-transform">
                <Sparkles className="w-4 h-4 text-white" strokeWidth={2.5} />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="font-display font-bold text-ink tracking-tight">
                  Realstate
                </span>
                <span className="text-[10px] text-ink-subtle uppercase tracking-wider -mt-0.5">
                  AI Reel Studio
                </span>
              </div>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <Link
                href="/"
                className="px-3 py-2 rounded-lg text-ink-muted hover:text-ink hover:bg-primary-50 transition-colors"
              >
                Projects
              </Link>
              <Link
                href="/templates"
                className="px-3 py-2 rounded-lg text-ink-muted hover:text-ink hover:bg-primary-50 transition-colors"
              >
                Templates
              </Link>
              <Link
                href="/projects/new"
                className="ml-2 px-4 py-2 rounded-lg text-sm font-medium text-white bg-gradient-brand shadow-brand-soft hover:shadow-brand transition-shadow"
              >
                New Reel
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
        <footer className="mx-auto max-w-7xl px-6 py-10 text-xs text-ink-subtle border-t border-border/40 mt-16">
          Built with FFmpeg, OpenAI, Nano Banana · Lifted from LTX-Video patterns
        </footer>
      </body>
    </html>
  );
}
