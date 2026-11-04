"""Outreach pitch writing goes through app/llm (route "pitch") with cost logging per outreach job (K2)."""

import importlib

import pytest

from app.llm import routes

# the nodes package re-exports functions under the module names, so load the modules explicitly
gen = importlib.import_module("app.outreach.nodes.generate_creator_pitch")
rep = importlib.import_module("app.outreach.nodes.repair_creator_pitch")
from app.schemas.outreach import PitchBundle

CREATOR = {"creator_id": "UC1", "creator_name": "Test Creator", "recent_videos": ["ML roadmap"]}


def fake_achat(calls):
    async def achat(route, messages, schema=None, *, context=None, temperature=None):
        calls.append({"route": route, "schema": schema, "context": context, "prompt": messages})
        return PitchBundle(creator_id="UC1", pitch_angle="their ML roadmap videos")
    return achat


@pytest.mark.asyncio
async def test_generate_uses_the_pitch_route_and_logs_cost_to_the_job(monkeypatch):
    calls = []
    monkeypatch.setattr(gen, "achat", fake_achat(calls))
    cmd = await gen.generate_creator_pitch({"outreach_job_id": "job-1", "campaign_id": "c1", "creator_input": CREATOR})
    assert calls[0]["route"] == "pitch" and calls[0]["schema"] is PitchBundle
    assert calls[0]["context"].run_id == "job-1" and calls[0]["context"].campaign_id == "c1"
    assert cmd.update["creator_pitch_bundles"]["UC1"]["pitch_angle"] == "their ML roadmap videos"
    sent = cmd.goto.arg
    assert sent["outreach_job_id"] == "job-1" and sent["campaign_id"] == "c1"  # passed on to validate -> repair


@pytest.mark.asyncio
async def test_repair_uses_the_pitch_route_and_logs_cost_to_the_job(monkeypatch):
    calls = []
    monkeypatch.setattr(rep, "achat", fake_achat(calls))
    state = {"outreach_job_id": "job-1", "campaign_id": "c1", "creator_input": CREATOR,
             "creator_pitch_bundles": {"UC1": {"creator_id": "UC1", "pitch_angle": "x"}},
             "creator_validations": {"UC1": {"errors": ["too long"], "passed": False}}, "creator_repair_counts": {"UC1": 0}}
    cmd = await rep.repair_creator_pitch(state)
    assert calls[0]["route"] == "pitch" and calls[0]["context"].run_id == "job-1"
    assert "too long" in calls[0]["prompt"]  # the validation errors are in the repair prompt
    assert cmd.update["creator_repair_counts"]["UC1"] == 1


def test_pitch_route_keeps_the_model_outreach_already_used():
    assert routes.route_models("pitch")[0].model == "gemini-3.5-flash-lite"
    assert routes.route_models("judge_eval")[0].model == "gemini-3.5-flash-lite"


def test_no_code_imports_the_old_hard_coded_model():
    with pytest.raises(ModuleNotFoundError):
        __import__("app.core.model")
