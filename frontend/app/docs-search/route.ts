import { createFromSource } from "fumadocs-core/search/server";
import { source } from "@/lib/source";

// Docs search. Not under /api/* because vercel.json sends /api/* to the backend.
export const { GET } = createFromSource(source);
