import { NextRequest, NextResponse } from "next/server";

/** A creator's tracking link: counts the visit (backend /api/links/{slug}) and sends people to the founder's site. */
export async function GET(req: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!/^[a-z0-9]{4,16}$/.test(slug)) return new NextResponse("Not found", { status: 404 });
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || req.nextUrl.origin;
  try {
    const r = await fetch(`${base}/api/links/${slug}`, {
      headers: { "user-agent": req.headers.get("user-agent") ?? "" }, // so link previews and bots aren't counted
      cache: "no-store",
    });
    if (!r.ok) return new NextResponse("This link doesn't exist.", { status: 404 });
    const { url } = (await r.json()) as { url?: string };
    if (!url || !/^https:\/\//.test(url)) return new NextResponse("This link doesn't exist.", { status: 404 });
    return NextResponse.redirect(url, 302);
  } catch {
    return new NextResponse("Try again in a moment.", { status: 502 });
  }
}
