"""Which model handles which task, with fallbacks (spec §3.2).

Each route is an ordered list of models; the client tries them in order (the fallback logic is ours, free).
Claude and GPT go through Vercel AI Gateway (no markup); Gemini and gpt-oss are called directly as backups.
Prices are USD per million tokens, from public price pages (Nov 2026); None = unknown,
so the cost is logged with tokens only. Verify before relying on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Provider = Literal["openai_compat", "google"]


@dataclass(frozen=True)
class ModelSpec:
    provider: Provider
    model: str
    vendor: str  # name logged in cost_events
    api_key_env: str  # one env var name, or several separated by "|" (the first one set is used)
    base_url: Optional[str] = None  # openai_compat only
    price_in: Optional[float] = None
    price_out: Optional[float] = None
    temperature: bool = True  # False: the model rejects a temperature setting (it's dropped)
    max_tokens: int = 4000  # output cap (a reasoning model's thinking counts too); never the provider's maximum
    reasoning_effort: Optional[str] = None  # reasoning models: "low" halves GPT-5 mini's time on short emails


# Vercel AI Gateway (decided Nov 15): one OpenAI-compatible endpoint for Claude, GPT and Gemini, no markup on
# tokens. Auth: an AI Gateway API key, or the Vercel deployment's OIDC token.
VERCEL_GATEWAY = "https://ai-gateway.vercel.sh/v1"
GATEWAY_KEY = "AI_GATEWAY_API_KEY|VERCEL_OIDC_TOKEN"

# Picked with a live test on Nov 15 (same reply task, 8 runs each, Jev-scored): Haiku 5.5 wrote the most natural
# replies after Sonnet, invented nothing, never failed, and is the cheapest good writer ($0.0003 per reply).
CLAUDE_HAIKU = ModelSpec(provider="openai_compat", model="anthropic/claude-haiku-5.5", vendor="vercel_gateway",
                         api_key_env=GATEWAY_KEY, base_url=VERCEL_GATEWAY, price_in=0.10, price_out=0.50, temperature=False)
GPT5_MINI = ModelSpec(provider="openai_compat", model="openai/gpt-5-mini", vendor="vercel_gateway",
                      api_key_env=GATEWAY_KEY, base_url=VERCEL_GATEWAY, price_in=0.25, price_out=2.00, temperature=False,
                      reasoning_effort="low")
# Gemini straight from Google (its own key): still answers when the gateway is down. 3.8 Flash failed 5/5 on
# Nov 15 (overloaded), 3.5 Flash 5/5 fine.
GEMINI_FLASH = ModelSpec(provider="google", model="gemini-3.5-flash", vendor="google", api_key_env="GOOGLE_API_KEY",
                         price_in=1.50, price_out=9.00)
GEMINI_FLASH_LITE = ModelSpec(provider="google", model="gemini-3.5-flash-lite", vendor="google", api_key_env="GOOGLE_API_KEY",
                              price_in=0.30, price_out=2.50)
GROQ_GPT_OSS = ModelSpec(provider="openai_compat", model="openai/gpt-oss-120b", vendor="groq", api_key_env="GROQ_API_KEY",
                         base_url="https://api.groq.com/openai/v1", price_in=0.15, price_out=0.60)
CEREBRAS_GPT_OSS = ModelSpec(provider="openai_compat", model="gpt-oss-120b", vendor="cerebras", api_key_env="CEREBRAS_API_KEY",
                             base_url="https://api.cerebras.ai/v1", price_in=0.35, price_out=0.75)

# Every route: the gateway's two models first, then two other companies straight (an outage anywhere in one
# provider never stops ReachAI). Same order everywhere, so behaviour is predictable.
WRITING = [CLAUDE_HAIKU, GPT5_MINI, GEMINI_FLASH, GROQ_GPT_OSS]
ROUTES: dict[str, list[ModelSpec]] = {
    "strategy": WRITING,
    "brief": WRITING,
    "pitch": WRITING,
    "reply": WRITING,
    "counter": WRITING,
    "style": [GPT5_MINI, CLAUDE_HAIKU, GEMINI_FLASH, GROQ_GPT_OSS],  # turning a founder's edit into a style rule
    "judge_eval": [GPT5_MINI, GEMINI_FLASH],  # a different family from the writer (independence)
    "fit_fallback": [GROQ_GPT_OSS, GEMINI_FLASH_LITE, CEREBRAS_GPT_OSS],  # only if Jev is down: fast and cheap
}


def key_for(spec: ModelSpec) -> Optional[str]:
    import os

    for name in spec.api_key_env.split("|"):
        if os.getenv(name):
            return os.getenv(name)
    return None


def route_models(route: str) -> list[ModelSpec]:
    try:
        return ROUTES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown LLM route '{route}'. Known routes: {sorted(ROUTES)}") from exc
