import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};

export default config;
