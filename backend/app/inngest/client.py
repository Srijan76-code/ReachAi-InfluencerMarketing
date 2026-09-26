import logging
import inngest

from app.core.config import INNGEST_APP_ID, INNGEST_EVENT_KEY, INNGEST_SIGNING_KEY

inngest_client = inngest.Inngest(
    app_id=INNGEST_APP_ID,
    logger=logging.getLogger("uvicorn"),
    event_key=INNGEST_EVENT_KEY,
    signing_key=INNGEST_SIGNING_KEY,
)