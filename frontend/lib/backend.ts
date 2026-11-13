/** Where the browser reaches the backend. On Vercel the backend is served on the same address (`/api/*`),
 * so previews work without their own setting; only local dev runs it on another port. */
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");
