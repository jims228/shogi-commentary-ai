import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack warned about multiple lockfiles; force root to the monorepo base so it picks the top-level pnpm-lock.yaml.
  turbopack: {
    root: "../..",
  },
  devIndicators: false,
};

export default nextConfig;
