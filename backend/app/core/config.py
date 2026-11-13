import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/reachai"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
LANGGRAPH_CHECKPOINTER_URL = os.getenv(
    "LANGGRAPH_CHECKPOINTER_URL",
    DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1),
)
INNGEST_APP_ID = os.getenv("INNGEST_APP_ID", "reach-ai")
INNGEST_EVENT_KEY = os.getenv("INNGEST_EVENT_KEY")
INNGEST_SIGNING_KEY = os.getenv("INNGEST_SIGNING_KEY") or (
    "signkey-dev-" + ("0" * 64) if os.getenv("INNGEST_DEV") == "1" else None
)
# --- LLM layer (app/llm) ---------------------------------------------------
# "direct": call providers in each route's fallback order (app/llm/routes.py).
# "gateway": send every call to the LangSmith LLM Gateway, which holds the fallback chains.
LLM_BACKEND = os.getenv("LLM_BACKEND", "direct")
LANGSMITH_GATEWAY_URL = os.getenv("LANGSMITH_GATEWAY_URL")

# --- Jev / TypeSafe (app/judge) --------------------------------------------
# TYPESAFE_API_KEY is read by the SDK itself; never pass it in code.
# Jev can be reached directly (TypeSafe key) or through OpenRouter (OpenRouter key, "sk-or-...").
# JEV_PROVIDER=auto picks OpenRouter when the key is an OpenRouter key.
JEV_PROVIDER = os.getenv("JEV_PROVIDER", "auto")  # auto | typesafe | openrouter
OPENROUTER_BASE_URL = "https://openrouter.ai/api"
# Pinned versions: thresholds are tuned against one model version, so it must not change silently.
JEV_MODEL_TYPESAFE = "jev-1.13.0"
JEV_MODEL_OPENROUTER = "typesafe/jev-1.14-20261014"
JEV_MODEL = os.getenv("JEV_MODEL")  # optional override of the pinned model for the chosen provider
JEV_MAX_CONCURRENCY = int(os.getenv("JEV_MAX_CONCURRENCY", "8"))
JEV_TIMEOUT_SECONDS = float(os.getenv("JEV_TIMEOUT_SECONDS", "10"))

# --- Platform data providers (later phases) --------------------------------
X_PROVIDER = os.getenv("X_PROVIDER", "twitterapi")  # twitterapi | official
# X search is on only when this is "1" and X_PROVIDER_API_KEY is set (twitterapi.io). Off: X is skipped
# and not charged for.
X_ENABLED = os.getenv("X_ENABLED", "0") == "1"
# twitterapi.io allows 20 requests/second once topped up; an account that never topped up gets 1 every 5 s.
X_REQUESTS_PER_SECOND = float(os.getenv("X_REQUESTS_PER_SECOND", "15"))
APIFY_TOKEN = os.getenv("APIFY_TOKEN") or os.getenv("APIFY_API_TOKEN")
# Instagram search is on only when this is "1" and APIFY_TOKEN is set. Off: Instagram is skipped and not
# charged for.
INSTAGRAM_ENABLED = os.getenv("INSTAGRAM_ENABLED", "0") == "1"

# --- Discovery engine ----------------------------------------------------------------
# "legacy" = old YouTube pipeline (app/my_agent); "graph" = new discovery graph (app/discovery).
# Flip to "graph" after the 3-brief comparison; removed once the old pipeline is deleted (F1.13).
