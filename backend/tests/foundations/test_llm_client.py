from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.llm import client
from app.llm.routes import GROQ_GPT_OSS, CEREBRAS_GPT_OSS, ROUTES


class Brief(BaseModel):
    reasoning: str


class FakeStructured:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    async def ainvoke(self, messages):
        return self.behaviour()


class FakeModel:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    def with_structured_output(self, schema, include_raw=False):
        assert include_raw
        return FakeStructured(self.behaviour)

    async def ainvoke(self, messages):
        return self.behaviour()["raw"]


def ok(text="Strong fit for the brand.", tokens=(1000, 200)):
    raw = AIMessage(content="{}", usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1], "total_tokens": sum(tokens)})
    return lambda: {"parsed": Brief(reasoning=text), "raw": raw, "parsing_error": None}


def unparseable():
    return lambda: {"parsed": None, "raw": AIMessage(content="not json"), "parsing_error": "bad json"}


def boom():
    def raise_():
        raise ConnectionError("provider down")
    return raise_


@pytest.fixture
def two_model_route(monkeypatch):
    monkeypatch.setitem(ROUTES, "test_route", [GROQ_GPT_OSS, CEREBRAS_GPT_OSS])
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("CEREBRAS_API_KEY", "k2")
    monkeypatch.setattr(client.config, "LLM_BACKEND", "direct")


def use_models(monkeypatch, by_vendor):
    calls = []

    def build(spec, temperature):
        calls.append(spec.vendor)
        return FakeModel(by_vendor[spec.vendor])

    monkeypatch.setattr(client, "_build_model", build)
    return calls


@pytest.mark.asyncio
async def test_primary_model_success_logs_cost(two_model_route, monkeypatch, cost_log):
    calls = use_models(monkeypatch, {"groq": ok()})
    result = await client.achat("test_route", "hi", schema=Brief)
    assert result.reasoning == "Strong fit for the brand."
    assert calls == ["groq"]
    assert len(cost_log) == 1
    rec = cost_log[0]
    assert (rec.provider, rec.route, rec.input_tokens, rec.output_tokens) == ("groq", "test_route", 1000, 200)
    # 1000 × 0.15/M + 200 × 0.60/M
    assert rec.usd == Decimal("0.000270")


@pytest.mark.asyncio
async def test_falls_back_on_provider_error(two_model_route, monkeypatch, cost_log):
    calls = use_models(monkeypatch, {"groq": boom(), "cerebras": ok("fallback")})
    result = await client.achat("test_route", "hi", schema=Brief)
    assert result.reasoning == "fallback"
    assert calls == ["groq", "cerebras"]
    assert [r.provider for r in cost_log] == ["cerebras"]


@pytest.mark.asyncio
async def test_retries_bad_parse_once_then_falls_back(two_model_route, monkeypatch, cost_log):
    calls = use_models(monkeypatch, {"groq": unparseable(), "cerebras": ok("second")})
    result = await client.achat("test_route", "hi", schema=Brief)
    assert result.reasoning == "second"
    assert calls == ["groq", "groq", "cerebras"]


@pytest.mark.asyncio
async def test_skips_models_without_keys(two_model_route, monkeypatch, cost_log):
    monkeypatch.delenv("GROQ_API_KEY")
    calls = use_models(monkeypatch, {"cerebras": ok()})
    await client.achat("test_route", "hi", schema=Brief)
    assert calls == ["cerebras"]


@pytest.mark.asyncio
async def test_raises_when_everything_fails(two_model_route, monkeypatch, cost_log):
    use_models(monkeypatch, {"groq": boom(), "cerebras": boom()})
    with pytest.raises(client.LLMUnavailableError):
        await client.achat("test_route", "hi", schema=Brief)
    assert cost_log == []


@pytest.mark.asyncio
async def test_gateway_mode_uses_single_gateway_model(monkeypatch, cost_log):
    monkeypatch.setattr(client.config, "LLM_BACKEND", "gateway")
    monkeypatch.setattr(client.config, "LANGSMITH_GATEWAY_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls")
    seen = []

    def build(spec, temperature):
        seen.append((spec.vendor, spec.model, spec.base_url))
        return FakeModel(ok())

    monkeypatch.setattr(client, "_build_model", build)
    await client.achat("brief", "hi", schema=Brief)
    assert seen == [("langsmith_gateway", "brief", "https://gateway.example/v1")]
    assert cost_log[0].usd is None  # price unknown behind the gateway


def test_unknown_route_is_an_error():
    with pytest.raises(ValueError):
        client.route_models("nope")
