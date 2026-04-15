import logging
import inngest

inngest_client = inngest.Inngest(
    app_id="reach-ai",
    logger=logging.getLogger("uvicorn"),
)