"""Benchmark the read endpoints the campaign pages call, against a database seeded by seed.py.

- Runs the real FastAPI app in-process (httpx ASGI transport); auth is bypassed by overriding
  get_current_user, in this script only.
- A small TCP proxy between the app and Postgres adds --delay-ms to each forwarded chunk in each
  direction, to model network round trips to a remote database. This is a simulation: real Neon
  latency differs; compare before/after runs at the same delay.
- Reports per endpoint: p50/p95 sequential, p95 with --concurrency requests at once, requests/s,
  and per request: SQL statements, new pool connections, new checkpointer (psycopg) connections.

    python -m scripts.bench.bench --campaign <bench_campaign from seed.py> \\
        --db postgresql://postgres@127.0.0.1:5433/reachai_bench --delay-ms 2 > after.json
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from urllib.parse import urlsplit

PROXY_PORT = 6544


async def _pipe(reader, writer, delay):
    try:
        while data := await reader.read(65536):
            if delay:
                await asyncio.sleep(delay)
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()


async def main(args) -> dict:
    db = urlsplit(args.db)
    delay = args.delay_ms / 1000

    async def handle(cr, cw):
        sr, sw = await asyncio.open_connection(db.hostname, db.port or 5432)
        await asyncio.gather(_pipe(cr, sw, delay), _pipe(sr, cw, delay))

    server = await asyncio.start_server(handle, "127.0.0.1", PROXY_PORT)
    proxied = f"{db.username}@127.0.0.1:{PROXY_PORT}{db.path}"
    os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{proxied}"
    os.environ["LANGGRAPH_CHECKPOINTER_URL"] = f"postgresql://{proxied}"
    os.environ.setdefault("GOOGLE_API_KEY", "x")
    os.environ.setdefault("INNGEST_DEV", "1")

    t0 = time.perf_counter()
    from app.main import app
    import_s = time.perf_counter() - t0

    import httpx
    import psycopg
    from sqlalchemy import event

    from app.auth import user as auth
    from app.db.database import engine

    counts = {"sql": 0, "pool_connect": 0, "extra_connect": 0}
    event.listen(engine.sync_engine, "before_cursor_execute", lambda *a, **k: counts.__setitem__("sql", counts["sql"] + 1))
    event.listen(engine.sync_engine.pool, "connect", lambda *a, **k: counts.__setitem__("pool_connect", counts["pool_connect"] + 1))
    real_connect = psycopg.AsyncConnection.connect.__func__

    async def counting_connect(cls, *a, **k):
        counts["extra_connect"] += 1
        return await real_connect(cls, *a, **k)
    psycopg.AsyncConnection.connect = classmethod(counting_connect)

    async def bench_user():
        return {"sub": "bench-clerk"}
    app.dependency_overrides[auth.get_current_user] = bench_user

    cid = args.campaign
    endpoints = {
        "list campaigns": "/api/campaigns/",
        "campaign leads": f"/api/campaigns/{cid}/leads",
        "campaign status": f"/api/campaigns/{cid}/status",
        "campaign details": f"/api/campaigns/{cid}/details",
        "saved leads": f"/api/saved/?campaign_id={cid}",
        "latest outreach": f"/api/outreach/campaigns/{cid}/latest-job",
    }
    out = {"label": args.label, "simulated_db_delay_ms_each_way": args.delay_ms, "app_import_s": round(import_s, 2),
           "requests_per_endpoint": args.n, "concurrency": args.concurrency, "endpoints": {}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bench") as client:
        for name, path in endpoints.items():
            r = await client.get(path)  # warm-up, like a warm function instance
            size = len(r.content)
            before = dict(counts)
            seq = []
            for _ in range(args.n):
                t = time.perf_counter()
                await client.get(path)
                seq.append((time.perf_counter() - t) * 1000)
            per_req = {k: round((counts[k] - before[k]) / args.n, 2) for k in counts}
            conc = []
            sem = asyncio.Semaphore(args.concurrency)

            async def one():
                async with sem:
                    t = time.perf_counter()
                    await client.get(path)
                    conc.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            await asyncio.gather(*(one() for _ in range(args.n)))
            wall = time.perf_counter() - t
            q, cq = statistics.quantiles(seq, n=20), statistics.quantiles(conc, n=20)
            out["endpoints"][name] = {"status": r.status_code, "response_kb": round(size / 1024, 1),
                                      "p50_ms": round(q[9], 1), "p95_ms": round(q[18], 1),
                                      "concurrent_p95_ms": round(cq[18], 1), "requests_per_s": round(args.n / wall, 1),
                                      **per_req}
    server.close()
    await engine.dispose()
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--campaign", required=True)
    p.add_argument("--db", required=True, help="postgresql://user@host:port/dbname of the seeded database")
    p.add_argument("--delay-ms", type=float, default=2.0)
    p.add_argument("-n", type=int, default=40)
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--label", default="run")
    print(json.dumps(asyncio.run(main(p.parse_args())), indent=1))
