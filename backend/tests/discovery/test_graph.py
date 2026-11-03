import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from app.discovery.brief import parse_brief
from app.discovery.graph import build_discovery_graph
from app.models.discovery_run import RunCandidate, RunStrategy
from tests.discovery.fakes import BRIEF, make_deps, use_recorded_limits


def initial(run_id="run-1"):
    return {"run_id": run_id, "campaign_id": "camp-1", "brief": parse_brief(BRIEF).to_dict()}


async def run(sf, deps, run_id="run-1", saver=None, input_=None, stream=False):
    app = build_discovery_graph().compile(checkpointer=saver or InMemorySaver())
    cfg = {"configurable": {"thread_id": run_id}}
    events = []
    if stream:
        async for ns, mode, chunk in app.astream(input_ if input_ is not None else initial(run_id), cfg, context=deps,
                                                 stream_mode=["updates", "custom"], subgraphs=True, durability="sync"):
            if mode == "custom":
                events.append(chunk)
        state = (await app.aget_state(cfg)).values
    else:
        state = await app.ainvoke(input_ if input_ is not None else initial(run_id), cfg, context=deps, durability="sync")
    return app, cfg, state, events


@pytest.mark.asyncio
async def test_full_run_produces_ranked_leads_in_the_legacy_shape(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, counters = make_deps(sf)
    _, _, state, events = await run(sf, deps, stream=True)

    leads = state["final_leads"]
    assert leads, state.get("warnings")
    scores = [l["final_score"] for l in leads]
    assert scores == sorted(scores, reverse=True)
    lead = leads[0]
    for key in ("id", "title", "subscribers", "metrics", "valuation", "recent_videos", "final_score", "deal_status",
                "score_breakdown", "llm_reasoning", "socials"):
        assert key in lead, key
    assert lead["id"].startswith("UC") and lead["platform"] == "youtube"
    assert set(lead["metrics"]) >= {"avg_views", "reliability", "engagement_rate", "trust_score", "forecast"}
    # reasons only for the top N
    n = parse_brief(BRIEF).creator_count
    assert sum(1 for l in leads if l["llm_reasoning"]) == min(n, len(leads))
    assert counters["llm:brief"] == min(n, len(leads)) and counters["llm:strategy"] == 1
    # streamed live leads and stage notes
    assert any(e.get("type") == "leads" for e in events) and any(e.get("type") == "stage" for e in events)


@pytest.mark.asyncio
async def test_run_records_strategy_and_every_candidate(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf)
    _, _, state, _ = await run(sf, deps)
    async with sf() as s:
        strat = (await s.execute(select(RunStrategy))).scalar_one()
        rows = (await s.execute(select(RunCandidate).where(RunCandidate.run_id == "run-1"))).scalars().all()
    assert strat.strategy["youtube_queries"]
    stages = {r.stage for r in rows}
    assert "scored" in stages
    assert all(r.drop_reason for r in rows if r.stage == "filtered_out")


@pytest.mark.asyncio
async def test_platforms_not_built_yet_are_skipped_with_a_warning(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf)
    _, _, state, _ = await run(sf, deps)
    assert state["platforms"]["youtube"]["mode"] == "full"
    assert state["platforms"]["instagram"]["selected"] and state["platforms"]["instagram"]["mode"] is None
    assert any("instagram isn't available yet" in w for w in state["warnings"])
    assert [b["platform"] for b in state["branch_runs"]] == ["youtube"]


@pytest.mark.asyncio
async def test_unknown_country_codes_are_reported_not_trusted(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    brief = {**BRIEF, "constraints": {**BRIEF["constraints"], "target_countries": ["IN", "UN"]}}
    deps, _ = make_deps(sf)
    _, _, state, _ = await run(sf, deps, input_={"run_id": "r", "brief": parse_brief(brief).to_dict()}, run_id="r")
    assert any("UN" in w for w in state["warnings"])


@pytest.mark.asyncio
async def test_crash_mid_run_resumes_from_the_checkpoint(sf, monkeypatch, cost_log):
    """The judge step crashes after search and fetch finished. Resuming with None continues at
    judging: no new search, no new strategy call, and no duplicated candidates."""
    use_recorded_limits(monkeypatch)
    from app.discovery import graph as G

    monkeypatch.setattr(G, "API_RETRY", None)  # let the crash reach the runner on the first failure
    saver = InMemorySaver()
    deps, counters = make_deps(sf, fail_judge_times=10_000)
    with pytest.raises(Exception):
        await run(sf, deps, saver=saver)
    app = build_discovery_graph().compile(checkpointer=saver)
    cfg = {"configurable": {"thread_id": "run-1"}}
    pending = (await app.aget_state(cfg)).next
    assert pending  # stopped with work left

    adapters_before, strategy_before = counters.get("adapter_created", 0), counters["llm:strategy"]
    deps2, _ = make_deps(sf, counters=counters)  # judge works now
    state = await app.ainvoke(None, cfg, context=deps2, durability="sync")
    assert state["final_leads"]
    assert counters["llm:strategy"] == strategy_before  # strategy not redone
    assert counters["adapter_created"] - adapters_before <= 1  # only the judge step's branch resumed; no new search
    ids = [l["creator_id"] for l in state["final_leads"]]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_second_run_reuses_strategy_and_jev_answers(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, counters = make_deps(sf)
    await run(sf, deps, run_id="run-a")
    judged_first = counters["creator_judge"]
    await run(sf, deps, run_id="run-b")
    assert counters["llm:strategy"] == 1  # identical brief -> strategy reused
    assert counters["creator_judge"] == judged_first  # creators unchanged -> every Jev answer from the cache


@pytest.mark.asyncio
async def test_jev_down_for_platform_check_falls_back_to_preset(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf, jev_down=True)
    _, _, state, _ = await run(sf, deps)
    selected = sorted(p for p, v in state["platforms"].items() if v["selected"])
    assert selected == ["instagram", "youtube"]  # consumer preset
    assert state["final_leads"]


@pytest.mark.asyncio
async def test_reason_failure_leaves_an_empty_reason_not_a_failed_run(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf)
    calls = {"n": 0}
    real = deps.llm

    async def flaky(route, prompt, schema):
        if route == "brief":
            calls["n"] += 1
            raise RuntimeError("llm down")
        return await real(route, prompt, schema)

    deps.llm = flaky
    _, _, state, _ = await run(sf, deps)
    assert state["final_leads"] and all(l["llm_reasoning"] == "" for l in state["final_leads"])


@pytest.mark.asyncio
async def test_no_selected_platform_still_finishes(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf)
    deps.adapters = {}  # nothing built
    _, _, state, _ = await run(sf, deps)
    assert state["final_leads"] == [] and any("isn't available yet" in w for w in state["warnings"])


# --- probe then expand ------------------------------------------------------------------------------------

class FakeProbeAdapter:
    """A second platform with configurable creators, to exercise probe -> expand."""

    platform = "x"

    def __init__(self, calls, strong: bool):
        self.calls, self.strong = calls, strong
        self.warnings, self.dropped = [], {}

    async def source_candidates(self, strategy, limits):
        from app.platforms.base import CandidateRef

        self.calls.append(limits.max_queries)
        return [CandidateRef("x", f"x{i}", "search") for i in range(3)]

    async def fetch_profiles(self, refs, constraints=None):
        from tests.shared_core.factories import post, profile
        from scripts.record_youtube_fixtures import RECORDED_AT

        topic = "machine learning interview prep for freshers" if self.strong else "funny cat compilation"
        out = []
        for r in refs:
            posts = [post(i, views=80_000, days_ago=1 + i * 3, text=f"{topic} part {i}") for i in range(12)]
            p = profile(platform="x", platform_id=r.platform_id, followers=60_000, posts=posts, fetched_at=RECORDED_AT)
            p["display_name"] = f"X creator {r.platform_id}"
            out.append(p)
        return out

    def cheap_filter(self, profile, constraints):
        return True, None

    def priors(self):
        return None

    def estimate_cost_usd(self, limits):
        return 0.0


def with_probe_platform(deps, calls, strong):
    """X is not in the consumer preset, so when selected it runs as a probe."""
    deps.adapters = {**deps.adapters, "x": lambda: FakeProbeAdapter(calls, strong)}
    return deps


@pytest.mark.asyncio
async def test_strong_probe_is_expanded_and_its_creators_compete(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf, yes_platforms=("youtube", "x"))
    calls = []
    with_probe_platform(deps, calls, strong=True)
    _, _, state, _ = await run(sf, deps)
    runs = {(b["platform"], b["mode"]) for b in state["branch_runs"]}
    assert ("x", "probe") in runs and ("x", "expand") in runs  # probe beat the top list -> expanded once
    assert calls == [2, 6]  # probe used the small budget, expansion the larger one
    assert any(l["platform"] == "x" for l in state["final_leads"])


@pytest.mark.asyncio
async def test_weak_probe_is_not_expanded(sf, monkeypatch, cost_log):
    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf, yes_platforms=("youtube", "x"))
    calls = []
    with_probe_platform(deps, calls, strong=False)
    _, _, state, _ = await run(sf, deps)
    runs = {(b["platform"], b["mode"]) for b in state["branch_runs"]}
    assert ("x", "probe") in runs and ("x", "expand") not in runs
    assert calls == [2]


@pytest.mark.asyncio
async def test_branches_run_in_parallel_not_one_after_another(sf, monkeypatch, cost_log):
    """YouTube (full) and X (probe) searches overlap in time."""
    import asyncio, time

    use_recorded_limits(monkeypatch)
    deps, _ = make_deps(sf, yes_platforms=("youtube", "x"))
    spans = {}

    def slow(factory, name):
        def make():
            a = factory()
            real = a.source_candidates

            async def timed(strategy, limits):
                start = time.perf_counter()
                await asyncio.sleep(0.3)
                out = await real(strategy, limits)
                spans.setdefault(name, (start, time.perf_counter()))
                return out
            a.source_candidates = timed
            return a
        return make

    calls = []
    deps.adapters = {"youtube": slow(deps.adapters["youtube"], "youtube"),
                     "x": slow(lambda: FakeProbeAdapter(calls, strong=False), "x")}
    await run(sf, deps)
    (a0, a1), (b0, b1) = spans["youtube"], spans["x"]
    assert a0 < b1 and b0 < a1  # the two searches overlapped
