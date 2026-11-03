"""The only way code calls an LLM (CLAUDE.md rule 4, spec §3.1).

    result = await achat("brief", messages, schema=BriefModel, context=CostContext(run_id=...))

- `route` picks the model list in app/llm/routes.py.
- With `schema`, the reply is parsed into that Pydantic model. A parse failure is retried
  once on the same model, then the next model in the route is tried.
- Every successful call logs a cost_events row.
- LLM_BACKEND=gateway sends everything to the LangSmith LLM Gateway instead, which holds
  the fallback chains. The gateway is in beta, so "direct" stays available.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Optional, Sequence, TypeVar, Union

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from app.billing.costs import CostContext, CostRecord, record_cost, token_cost
from app.core import config
from app.llm.routes import ModelSpec, route_models

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Messages = Union[str, Sequence[BaseMessage]]

PARSE_ATTEMPTS_PER_MODEL = 2


class LLMUnavailableError(RuntimeError):
    """Every model in the route failed or had no API key configured."""


def _gateway_spec(route: str) -> ModelSpec:
    if not config.LANGSMITH_GATEWAY_URL:
        raise LLMUnavailableError("LLM_BACKEND=gateway but LANGSMITH_GATEWAY_URL is not set")
    return ModelSpec(
        provider="openai_compat",
        model=os.getenv(f"LLM_GATEWAY_ROUTE_{route.upper()}", route),
        vendor="langsmith_gateway",
        api_key_env="LANGSMITH_API_KEY",
        base_url=config.LANGSMITH_GATEWAY_URL,
    )


def _candidate_specs(route: str) -> list[ModelSpec]:
    if config.LLM_BACKEND == "gateway":
        return [_gateway_spec(route)]
    return route_models(route)


@lru_cache(maxsize=64)
def _build_model(spec: ModelSpec, temperature: Optional[float]):
    """Create (and reuse) a LangChain chat model. Retries are kept low so fallbacks kick in fast."""
    api_key = os.getenv(spec.api_key_env)
    kwargs: dict[str, Any] = {"model": spec.model, "max_retries": 1}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if spec.provider == "openai_compat":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(base_url=spec.base_url, api_key=api_key, **kwargs)
    if spec.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(google_api_key=api_key, **kwargs)
    raise ValueError(f"Unsupported provider {spec.provider}")


def _usage(message: Optional[AIMessage]) -> tuple[Optional[int], Optional[int]]:
    usage = getattr(message, "usage_metadata", None) or {}
    return usage.get("input_tokens"), usage.get("output_tokens")


async def _log_cost(spec: ModelSpec, route: str, message: Optional[AIMessage], context: CostContext) -> None:
    input_tokens, output_tokens = _usage(message)
    served_model = (getattr(message, "response_metadata", None) or {}).get("model_name")
    await record_cost(
        CostRecord(
            provider=spec.vendor,
            sku=served_model or spec.model,
            route=route,
            context=context,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usd=token_cost(input_tokens, output_tokens, spec.price_in, spec.price_out),
        )
    )


async def _call(spec: ModelSpec, messages: Messages, schema: Optional[type[T]], temperature: Optional[float]):
    """Returns (result, raw_message). Raises on transport errors or an unparseable reply."""
    model = _build_model(spec, temperature)
    if schema is None:
        message = await model.ainvoke(messages)
        return message.content, message
    structured = model.with_structured_output(schema, include_raw=True)
    out = await structured.ainvoke(messages)
    parsed, raw = out.get("parsed"), out.get("raw")
    if parsed is None:
        raise ValueError(f"Unparseable structured reply: {out.get('parsing_error')}")
    if not isinstance(parsed, schema):
        parsed = schema.model_validate(parsed)
    return parsed, raw


async def achat(
    route: str,
    messages: Messages,
    schema: Optional[type[T]] = None,
    *,
    context: Optional[CostContext] = None,
    temperature: Optional[float] = None,
) -> Union[T, str]:
    """Call the route's models in order until one succeeds."""
    context = context or CostContext()
    errors: list[str] = []
    for spec in _candidate_specs(route):
        if not os.getenv(spec.api_key_env):
            errors.append(f"{spec.vendor}/{spec.model}: {spec.api_key_env} not set")
            continue
        attempts = PARSE_ATTEMPTS_PER_MODEL if schema is not None else 1
        for attempt in range(1, attempts + 1):
            try:
                result, raw = await _call(spec, messages, schema, temperature)
            except ValueError as exc:  # bad structured output: retry the same model once
                errors.append(f"{spec.vendor}/{spec.model} attempt {attempt}: {exc}")
                continue
            except Exception as exc:  # provider/network error: move to the next model
                errors.append(f"{spec.vendor}/{spec.model}: {type(exc).__name__}: {exc}")
                break
            if errors:
                logger.warning("LLM route '%s' used fallback %s/%s after: %s", route, spec.vendor, spec.model, errors)
            await _log_cost(spec, route, raw, context)
            return result
    raise LLMUnavailableError(f"All models failed for route '{route}': {errors}")
