import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.discovery.runtime import STAGE_LABELS, mark_failed, run_discovery, thread_for
from app.models.campaign import Campaign, CampaignStatus
from app.models.user import User
from tests.discovery.conftest import TABLES
from tests.discovery.fakes import BRIEF, make_deps, use_recorded_limits


@pytest_asyncio.fixture
async def sfc(tmp_path):
    from tests.discovery.conftest import create_tables, make_engine

    engine, is_pg = make_engine(tmp_path)
    await create_tables(engine, is_pg, ["users", "campaigns"] + TABLES)
    f = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with f() as s:
        s.add(User(user_id="u1", clerk_id="clerk_1"))
        s.add(Campaign(campaign_id="c1", user_id="u1", campaign_details=BRIEF, status=CampaignStatus.PENDING))
        await s.commit()
    yield f
    await engine.dispose()


class Published(list):
    async def __call__(self, run_id, topic, data):
        self.append((topic, data))


async def campaign(sf):
    async with sf() as s:
        return (await s.execute(select(Campaign).where(Campaign.campaign_id == "c1"))).scalar_one()


@pytest.mark.asyncio
async def test_run_completes_and_updates_the_campaign(sfc, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sfc)
    pub = Published()
    out = await run_discovery(campaign_id="c1", run_id="r1", campaign_details=BRIEF, deps=deps,
                              checkpointer=InMemorySaver(), session_factory=sfc, publish=pub)
    c = await campaign(sfc)
    assert c.status == CampaignStatus.COMPLETED and c.campaign_leads == out["leads"] and out["leads"]
    assert c.thread_id == thread_for("r1") and c.workflow_status["engine"] == "graph"
    stages = [d["stage"] for t, d in pub if t == "status"]
    assert stages[-1] == "completed" and STAGE_LABELS["strategy"] in stages
    assert any(t == "leads" for t, _ in pub)
    assert out["resumed"] is False


@pytest.mark.asyncio
async def test_second_attempt_resumes_instead_of_restarting(sfc, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    from app.discovery import graph as G

    monkeypatch.setattr(G, "API_RETRY", None)
    saver = InMemorySaver()
    deps, counters = make_deps(sfc, fail_judge_times=10_000)
    with pytest.raises(Exception):
        await run_discovery(campaign_id="c1", run_id="r2", campaign_details=BRIEF, deps=deps, checkpointer=saver,
                            session_factory=sfc, publish=Published())
    c = await campaign(sfc)
    assert c.status == CampaignStatus.PENDING  # not marked failed: Inngest will retry

    deps2, counters2 = make_deps(sfc)
    out = await run_discovery(campaign_id="c1", run_id="r2", campaign_details=BRIEF, deps=deps2, checkpointer=saver,
                              session_factory=sfc, publish=Published())
    assert out["resumed"] is True and out["leads"]
    assert counters2.get("llm:strategy", 0) == 0  # strategy came from the checkpoint
    assert (await campaign(sfc)).status == CampaignStatus.COMPLETED


@pytest.mark.asyncio
async def test_mark_failed_after_last_retry(sfc):
    pub = Published()
    await mark_failed(campaign_id="c1", run_id="r3", error="boom " * 500, session_factory=sfc, publish=pub)
    c = await campaign(sfc)
    assert c.status == CampaignStatus.CREATED and c.workflow_status["status"] == "failed"
    assert len(c.workflow_status["error"]) <= 500
    assert pub[-1][1]["status"] == "failed"


@pytest.mark.asyncio
async def test_failure_handler_reads_the_original_event(monkeypatch):
    from types import SimpleNamespace

    from app.inngest import functions as F

    seen = {}

    async def fake_mark(**kw):
        seen.update(kw)

    monkeypatch.setattr("app.discovery.runtime.mark_failed", fake_mark)
    ctx = SimpleNamespace(event=SimpleNamespace(data={"event": {"data": {"campaign_id": "c9", "run_id": "r9"}},
                                                      "error": {"message": "quota"}}))
    await F._campaign_run_failed(ctx)
    assert seen == {"campaign_id": "c9", "run_id": "r9", "error": "quota"}
    seen.clear()
    await F._campaign_run_failed(SimpleNamespace(event=SimpleNamespace(data={})))
    assert seen == {}


@pytest.mark.asyncio
async def test_campaign_run_always_uses_the_discovery_graph(monkeypatch):
    """The old pipeline is gone: every campaign/run event runs (or resumes) the discovery graph."""
    from types import SimpleNamespace

    from app.discovery import runtime as R
    from app.inngest import functions as F

    seen = {}

    async def fake_run(**kw):
        seen.update(kw)
        return {"leads": [{"id": "UC1"}], "warnings": [], "resumed": True}

    monkeypatch.setattr(R, "run_discovery", fake_run)
    ctx = SimpleNamespace(event=SimpleNamespace(data={"campaign_id": "c1", "campaign_details": BRIEF, "run_id": "r1", "user_id": "u1"}))
    out = await F.run_campaign._handler(ctx)
    assert seen == {"campaign_id": "c1", "run_id": "r1", "campaign_details": BRIEF, "user_id": "u1"}
    assert out["leads"] == 1 and out["resumed"] is True
    with pytest.raises(ModuleNotFoundError):
        __import__("app.my_agent")



@pytest.mark.asyncio
@pytest.mark.skipif(not __import__("os").getenv("PG_TEST_URL"), reason="needs PG_TEST_URL (real Postgres)")
async def test_resume_works_across_separate_postgres_checkpointers(sfc, monkeypatch, cost_log):
    """Crash in one 'request', resume in another with a brand-new Postgres checkpointer connection."""
    import os

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from app.discovery import graph as G

    use_recorded_limits(monkeypatch)
    monkeypatch.setattr(G, "API_RETRY", None)
    url = os.environ["PG_TEST_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    run_id = "pg-resume-1"

    deps, _ = make_deps(sfc, fail_judge_times=10_000)
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        await saver.setup()
        await saver.adelete_thread(thread_for(run_id))
        with pytest.raises(Exception):
            await run_discovery(campaign_id="c1", run_id=run_id, campaign_details=BRIEF, deps=deps,
                                checkpointer=saver, session_factory=sfc, publish=Published())

    deps2, counters2 = make_deps(sfc)
    async with AsyncPostgresSaver.from_conn_string(url) as saver2:  # new connection, like a new request
        out = await run_discovery(campaign_id="c1", run_id=run_id, campaign_details=BRIEF, deps=deps2,
                                  checkpointer=saver2, session_factory=sfc, publish=Published())
        await saver2.adelete_thread(thread_for(run_id))
    assert out["resumed"] is True and out["leads"]
    assert counters2.get("llm:strategy", 0) == 0


@pytest.mark.asyncio
async def test_default_youtube_adapter_caches_in_the_runs_database(sfc, monkeypatch):
    """The adapter's search cache must use the run's session factory, set after the deps are built."""
    from app.billing.costs import CostContext
    from app.discovery import cache as C
    from app.discovery.runtime import default_deps

    used = []

    async def fake_cached(namespace, key, ttl, compute, *, session_factory=None):
        used.append(session_factory)
        return await compute(), False

    monkeypatch.setattr(C, "cached", fake_cached)
    deps = default_deps(CostContext())
    deps.session_factory = sfc  # what run_discovery does
    adapter = deps.adapters["youtube"]()
    assert deps.adapters["youtube"]().api is adapter.api  # one shared HTTP client per run

    class API:
        async def search(self, **p):
            return {"items": []}

    adapter.api = API()
    from app.platforms.base import Limits

    await adapter._search("channel", "ml", Limits())
    assert used == [sfc]


def test_every_inngest_function_fits_the_plan_limits():
    """Inngest rejects the whole app sync if any function asks for more concurrency than the plan
    allows (this silently kept the nightly refresh and keep-warm functions unregistered)."""
    from app.discovery import limits as L
    from app.inngest import functions as F
    from app.main import app  # noqa: F401  (the served list)
    import inngest

    fns = [v for v in vars(F).values() if isinstance(v, inngest.Function)]
    ids = {f.id for f in fns}
    for name in ("run_campaign", "run_outreach", "refresh_youtube_data", "keep_backend_warm"):
        assert any(i.endswith(name) for i in ids), (name, ids)
    for f in fns:
        for c in f.get_config("http://x/api/inngest").main.concurrency or []:
            assert c.limit <= L.INNGEST_PLAN_MAX_CONCURRENCY, (f.id, c)
