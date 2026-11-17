"""Brief from a website, live (F1.24b): Jina reads each site, the `brief_from_site` route fills the brief, Jev checks every
filled field. Prints one row per site and the brief it kept. Run from backend/:

    python scripts/benchmarks/site_brief.py                      # the ten default sites
    python scripts/benchmarks/site_brief.py acme.com other.io    # your own

Needs the keys of the route's models (the Vercel AI Gateway for Haiku 5.5, else GOOGLE_API_KEY / GROQ_API_KEY) and
TYPESAFE_API_KEY for Jev. Costs a few cents. Results: docs/MODEL_BENCHMARKS.md."""

import asyncio
import json
import logging
import sys
import time

logging.disable(logging.CRITICAL)

from app.discovery import site_brief as sb  # noqa: E402
from app.judge import client as jc  # noqa: E402

DEFAULT_SITES = ["cal.com", "plausible.io", "scrimba.com", "huel.com", "glossier.com", "strava.com", "mercury.com", "gumroad.com",
                 "superhuman.com", "beehiiv.com"]
sources: list = []
_real_judge = jc.judge


async def _spy(state, questions, **kw):  # which judge answered: real Jev or the plain-AI fallback
    j = await _real_judge(state, questions, **kw)
    sources.append((j.source, j.model))
    return j


jc.judge = _spy


async def one(raw: str) -> dict:
    row, started = {"site": raw}, time.time()
    sources.clear()
    try:
        url = sb.normalize_url(raw)
        page = await sb.read_page(url)
        row.update(read_s=round(time.time() - started, 1), chars=len(page))
        t = time.time()
        brief = await sb.extract(page, url)
        row["ai_s"] = round(time.time() - t, 1)
        filled = sb.filled_fields(brief)
        t = time.time()
        kept, confirmed, checked = await sb.verify(page, brief)
        row.update(jev_s=round(time.time() - t, 1), filled=filled, confirmed=confirmed, checked=checked,
                   cleared=[f for f in filled if f not in confirmed], judge=sources[0] if sources else None,
                   brief={k: v for k, v in kept.model_dump().items() if v})
    except sb.SiteReadError as exc:
        row["error"] = str(exc)
    return row


async def main() -> None:
    rows = [await one(s) for s in (sys.argv[1:] or DEFAULT_SITES)]
    print(f"{'site':16} {'read':>5} {'fill':>5} {'jev':>4}  {'judge':8} kept  cleared")
    for r in rows:
        if "error" in r:
            print(f"{r['site']:16} {r['error'][:110]}")
            continue
        print(f"{r['site']:16} {r['read_s']:5} {r['ai_s']:5} {r['jev_s']:4}  {(r['judge'] or ['-'])[0]:8} {len(r['confirmed'])}/{len(r['filled'])}   {r['cleared']}")
    print("\n" + "\n".join(json.dumps(r, ensure_ascii=False) for r in rows))


if __name__ == "__main__":
    asyncio.run(main())
