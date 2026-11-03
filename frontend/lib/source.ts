import { docs } from "@/.source/server";
import { loader } from "fumadocs-core/source";

// Single source for every docs page (content/docs → /docs/...).
export const source = loader({
  baseUrl: "/docs",
  source: docs.toFumadocsSource(),
});
