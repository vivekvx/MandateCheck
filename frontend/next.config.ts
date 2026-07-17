import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for Cloudflare Pages: no server runtime in this app —
  // every page is a static shell and all API/WebSocket calls happen
  // client-side against NEXT_PUBLIC_API_BASE_URL (baked in at build time).
  output: "export",
};

export default nextConfig;
