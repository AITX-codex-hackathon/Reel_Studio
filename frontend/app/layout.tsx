import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import Link from "next/link";
import Script from "next/script";
import { Sparkles } from "lucide-react";
import { Providers } from "@/components/Providers";
import { NewReelButton } from "@/components/auth/NewReelButton";
import { UserNav } from "@/components/auth/UserNav";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ReelStudio — AI Projects for Real Estate",
  description: "Turn property photos into cinematic projects powered by AI.",
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
        <Providers>
          <Script
            id="strip-extension-hydration-attrs"
            strategy="beforeInteractive"
            dangerouslySetInnerHTML={{ __html: stripExtensionAttributesScript }}
          />
          <header className="sticky top-0 z-40 glass">
            <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
              <Link href="/" className="flex items-center group relative">
                <img
                  src="/logo_transparent_fallback.png"
                  alt="ReelStudio Logo"
                  className="w-28 h-28 object-contain group-hover:scale-105 transition-transform mt-4"
                />
                <div className="flex flex-col leading-tight -ml-6 z-10">
                  <span className="font-display font-bold text-white tracking-tight text-xl drop-shadow-md">
                    ReelStudio
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
                <NewReelButton isHeader>New Project</NewReelButton>
                <UserNav />
              </nav>
            </div>
          </header>
          <main>{children}</main>
          <footer className="mx-auto max-w-7xl px-6 py-10 text-xs text-ink-subtle border-t border-white/[0.06] mt-16">
            &copy; {new Date().getFullYear()} Reelstate. All rights reserved.
          </footer>
        </Providers>
      </body>
    </html>
  );
}
