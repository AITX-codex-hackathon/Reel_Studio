import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import Link from "next/link";
import Script from "next/script";
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
  description: "Turn property photos into cinematic reels powered by AI.",
};

const stripExtensionAttributesScript = `
(() => {
  const prefix = "rtrvr-";

  const cleanNode = (node) => {
    if (!(node instanceof Element)) return;

    for (const attr of Array.from(node.attributes)) {
      if (attr.name.startsWith(prefix)) {
        node.removeAttribute(attr.name);
      }
    }
  };

  const cleanTree = (root) => {
    cleanNode(root);
    root.querySelectorAll?.("*").forEach(cleanNode);
  };

  cleanTree(document.documentElement);

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "attributes" && mutation.attributeName?.startsWith(prefix)) {
        mutation.target.removeAttribute(mutation.attributeName);
      }

      for (const node of mutation.addedNodes) {
        cleanTree(node);
      }
    }
  });

  observer.observe(document.documentElement, {
    attributes: true,
    childList: true,
    subtree: true,
  });

  window.addEventListener("load", () => {
    window.setTimeout(() => observer.disconnect(), 5000);
  });
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`} suppressHydrationWarning>
      <body className="min-h-screen font-sans" suppressHydrationWarning>
        <Script
          id="strip-extension-hydration-attrs"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: stripExtensionAttributesScript }}
        />
        <header className="sticky top-0 z-40 glass">
          <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-brand flex items-center justify-center shadow-brand-soft group-hover:scale-105 transition-transform">
                <Sparkles className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="font-display font-bold text-white tracking-tight text-lg">
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
                className="px-3 py-2 rounded-lg text-ink-muted hover:text-white hover:bg-white/[0.06] transition-colors"
              >
                Projects
              </Link>
              <Link
                href="/templates"
                className="px-3 py-2 rounded-lg text-ink-muted hover:text-white hover:bg-white/[0.06] transition-colors"
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
        <main>{children}</main>
        <footer className="mx-auto max-w-7xl px-6 py-10 text-xs text-ink-subtle border-t border-white/[0.06] mt-16">
          &copy; {new Date().getFullYear()} Realstate. All rights reserved.
        </footer>
      </body>
    </html>
  );
}
