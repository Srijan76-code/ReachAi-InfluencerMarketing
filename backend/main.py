from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import logging
import uuid
import time
import asyncio
import inngest
import inngest.fast_api

load_dotenv()

from schemas import CampaignGenerateRequest
from my_agent.agent import workflow

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
app = FastAPI(title="ReachAI Backend API")


FAKE_DB = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Inngest Client

inngest_client = inngest.Inngest(
    app_id="reach-ai",
    logger=logging.getLogger("uvicorn"),
)


# Inngest Function 

@inngest_client.create_function(
    fn_id="run_campaign",
    trigger=inngest.TriggerEvent(event="campaign/run"),
)
async def run_campaign(ctx: inngest.Context):

    campaign_id = ctx.event.data["campaign_id"]
    campaign_details= ctx.event.data["campaign_details"]
    logger.info(f"[Inngest] Received job for campaign_id={campaign_id}")

    try:

        config = {
            "configurable": {
                "thread_id": campaign["thread_id"]
            }
        }

        # Simulate delay (optional)
        await asyncio.sleep(20)

        # Run LangGraph
        # result = await workflow.ainvoke(campaign_details, config)
        result= "This is a test result"

        # Save result
        campaign["status"] = "COMPLETED"
        campaign["result"] = result

        logger.info(f"[DB] {campaign_id} → COMPLETED")

    except Exception as e:
        campaign["status"] = "FAILED"
        campaign["error"] = str(e)

        logger.error(f"[DB] {campaign_id} → FAILED: {e}")

    return campaign["result"]



# API ROUTES
@app.get("/health")
def health_check():
    return {"status": "healthy"}


# 1. Create Campaign → Trigger Inngest
@app.post("/api/campaigns/generate")
async def generate_campaign(request: CampaignGenerateRequest):
    try:
        campaign_id = str(uuid.uuid4())

        payload = request.model_dump()

        thread_id = str(uuid.uuid4())

        # Save to fake DB
        FAKE_DB[campaign_id] = {
            "id": campaign_id,
            "status": "PENDING",
            "input": payload,
            "thread_id": thread_id,
            "result": None,
        }

        logger.info(f"[DB] {campaign_id} → PENDING")

        # Send event to Inngest
        await inngest_client.send(
            inngest.Event(
                name="campaign/run",
                data={"campaign_id": campaign_id, campaign_details:payload},
            )
        )

        return {
            "success": True,
            "campaign_id": campaign_id
            
        }

    except Exception as e:
        logger.error(f"Error creating campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# 2. Poll Campaign Status
@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: str):
    campaign = FAKE_DB.get(campaign_id)


    if not campaign:
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "status": campaign["status"],
        "result": campaign.get("result"),
        "error": campaign.get("error"),
    }



# Inngest Serve
inngest.fast_api.serve(app, inngest_client, [run_campaign])



# Run Server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




