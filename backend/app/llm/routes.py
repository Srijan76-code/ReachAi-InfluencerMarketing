"""Which model handles which task, with fallbacks (spec §3.2).

Each route is an ordered list of models. In "direct" mode the client tries them in order;
in "gateway" mode the LangSmith LLM Gateway holds the chain and we call it by route name.

Picking the final model for each route is done with the LangSmith eval suite
(roadmap: record the winning eval run next to each change here).
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
    api_key_env: str
    base_url: Optional[str] = None  # openai_compat only
    price_in: Optional[float] = None
    price_out: Optional[float] = None


GROQ_GPT_OSS = ModelSpec(
    provider="openai_compat",
    model="openai/gpt-oss-120b",
    vendor="groq",
    api_key_env="GROQ_API_KEY",
    base_url="https://api.groq.com/openai/v1",
    price_in=0.15,
    price_out=0.60,
)
CEREBRAS_GPT_OSS = ModelSpec(
    provider="openai_compat",
    model="gpt-oss-120b",
    vendor="cerebras",
    api_key_env="CEREBRAS_API_KEY",
    base_url="https://api.cerebras.ai/v1",
    price_in=0.35,
    price_out=0.75,
)
GEMINI_FLASH_LITE = ModelSpec(
    provider="google",
    model="gemini-3.5-flash-lite",  # the model outreach has used so far
    vendor="google",
    api_key_env="GOOGLE_API_KEY",
)
GEMINI_FLASH = ModelSpec(
    provider="google",
    model="gemini-3.8-flash",
    vendor="google",
    api_key_env="GOOGLE_API_KEY",
)

# Until the evals pick a frontier model for `strategy` / `pitch` / `reply`, the current
# Gemini models stay first so behaviour doesn't change, with gpt-oss as the fallback.
ROUTES: dict[str, list[ModelSpec]] = {
    "strategy": [GEMINI_FLASH, GROQ_GPT_OSS, CEREBRAS_GPT_OSS],
    "brief": [GROQ_GPT_OSS, CEREBRAS_GPT_OSS, GEMINI_FLASH_LITE],
    "pitch": [GEMINI_FLASH_LITE, GROQ_GPT_OSS],  # unchanged model until K3's evals pick one
    "reply": [GEMINI_FLASH, GROQ_GPT_OSS],
    "judge_eval": [GEMINI_FLASH_LITE],
    "fit_fallback": [GROQ_GPT_OSS, CEREBRAS_GPT_OSS, GEMINI_FLASH_LITE],
}


def route_models(route: str) -> list[ModelSpec]:
    try:
        return ROUTES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown LLM route '{route}'. Known routes: {sorted(ROUTES)}") from exc
