import { defineConfig, defineDocs } from "fumadocs-mdx/config";

// Docs live in content/docs as MDX. Update them whenever a feature ships (see CLAUDE.md).
export const docs = defineDocs({
  dir: "content/docs",
});

export default defineConfig();
