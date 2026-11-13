"""SMALL_SEARCHES=1 keeps test searches inside free provider tiers."""

import importlib


def test_small_searches_shrink_every_mode(monkeypatch):
    import app.discovery.limits as L

    monkeypatch.setenv("SMALL_SEARCHES", "1")
    small = importlib.reload(L)
    try:
        assert small.SMALL_SEARCHES
        assert all(lim.max_queries == 2 and lim.max_candidates == 30 and lim.max_profiles == 10
                   for lim in small.LIMITS_BY_MODE.values())
    finally:
        monkeypatch.delenv("SMALL_SEARCHES")
        assert importlib.reload(L).LIMITS_BY_MODE["full"].max_profiles == 150


def test_small_searches_skip_the_top_up_round(monkeypatch):
    from app.discovery import limits as L
    from app.discovery import nodes

    monkeypatch.setattr(L, "SMALL_SEARCHES", True)
    assert nodes.needs_top_up({"mode": "full", "measured": []}) == "shortlist"
