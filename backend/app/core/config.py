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