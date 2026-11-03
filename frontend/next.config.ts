import type { NextConfig } from "next";
import { createMDX } from "fumadocs-mdx/next";

const nextConfig: NextConfig = {
  /* config options here */
};

// Compiles the MDX docs in content/docs (served at /docs).
const withMDX = createMDX();

export default withMDX(nextConfig);
