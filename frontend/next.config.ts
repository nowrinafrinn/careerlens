import type { NextConfig } from "next";

// Where the FastAPI backend listens. The browser never talks to it directly:
// it calls /api/... on the Next.js origin, and Next forwards the request.
// That keeps one origin for the browser, so the login cookie (Milestone 2)
// needs no CORS or cross-site cookie setup.
// Note: rewrites are resolved at build time, so set API_URL before `next build`.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // A self-contained server (.next/standalone) for the production Docker image.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
